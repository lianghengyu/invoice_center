import os
import csv
import json
import torch
import numpy as np
from torch.utils.data import Dataset
from torchvision.models.detection import fasterrcnn_resnet50_fpn, FasterRCNN_ResNet50_FPN_Weights
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.transforms import functional as F
from torchvision.transforms import transforms as T
from PIL import Image
import torch.optim as optim
from torch.utils.data import DataLoader
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data/fasterrcnn")
MODEL_SAVE = os.path.join(BASE_DIR, "model/fasterrcnn")

CLASS_NAMES = [
    '__background__',
    '发票代码', '发票号码', '发票日期',
    '购买方名称', '购买方纳税人识别号',
    '价税合计', '增值税电子普通发票',
    '发票',
]


class Compose:
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, image, target):
        for t in self.transforms:
            image, target = t(image, target)
        return image, target


class RandomHorizontalFlip:
    def __init__(self, prob=0.5):
        self.prob = prob

    def __call__(self, image, target):
        if torch.rand(1).item() < self.prob:
            w, h = image.size
            image = F.hflip(image)
            boxes = target['boxes']
            boxes[:, [0, 2]] = w - boxes[:, [2, 0]]
            target['boxes'] = boxes
        return image, target


class ToTensor:
    def __call__(self, image, target):
        image = F.to_tensor(image)
        return image, target


class InvoiceDataset(Dataset):
    def __init__(self, img_dir, ann_dir, transforms=None):
        self.img_dir = img_dir
        self.ann_dir = ann_dir
        self.transforms = transforms
        self.img_files = sorted([
            f for f in os.listdir(img_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ])

    def __len__(self):
        return len(self.img_files)

    def __getitem__(self, idx):
        img_name = self.img_files[idx]
        img_path = os.path.join(self.img_dir, img_name)
        ann_path = os.path.join(self.ann_dir, os.path.splitext(img_name)[0] + ".pt")

        img = Image.open(img_path).convert("RGB")
        target = torch.load(ann_path, weights_only=True)

        if self.transforms is not None:
            img, target = self.transforms(img, target)

        return img, target


def collate_fn(batch):
    return tuple(zip(*batch))


def compute_map_at_iou(predictions, targets, iou_threshold=0.5, score_threshold=0.3):
    num_classes = len(CLASS_NAMES) - 1
    tp = np.zeros(num_classes)
    fp = np.zeros(num_classes)
    fn = np.zeros(num_classes)

    for pred, target in zip(predictions, targets):
        gt_boxes = target['boxes'].cpu().numpy()
        gt_labels = target['labels'].cpu().numpy()

        scores = pred['scores'].cpu().numpy()
        keep = scores >= score_threshold
        pred_boxes = pred['boxes'].cpu().numpy()[keep]
        pred_labels = pred['labels'].cpu().numpy()[keep]

        matched_gt = set()
        for i in range(len(pred_boxes)):
            pb = pred_boxes[i]
            pl = pred_labels[i] - 1
            if pl < 0 or pl >= num_classes:
                continue

            best_iou = 0
            best_j = -1
            for j in range(len(gt_boxes)):
                if j in matched_gt:
                    continue
                gb = gt_boxes[j]
                gl = gt_labels[j] - 1
                if gl != pl:
                    continue
                ix1 = max(pb[0], gb[0])
                iy1 = max(pb[1], gb[1])
                ix2 = min(pb[2], gb[2])
                iy2 = min(pb[3], gb[3])
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = (pb[2]-pb[0])*(pb[3]-pb[1]) + (gb[2]-gb[0])*(gb[3]-gb[1]) - inter
                iou = inter / union if union > 0 else 0
                if iou > best_iou:
                    best_iou = iou
                    best_j = j

            if best_iou >= iou_threshold and best_j >= 0:
                tp[pl] += 1
                matched_gt.add(best_j)
            else:
                fp[pl] += 1

        for j in range(len(gt_boxes)):
            if j not in matched_gt:
                gl = gt_labels[j] - 1
                if 0 <= gl < num_classes:
                    fn[gl] += 1

    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    ap_per_class = tp / (tp + fp + fn + 1e-8)

    return float(np.mean(precision)), float(np.mean(recall)), float(np.mean(ap_per_class))


def main():
    os.makedirs(MODEL_SAVE, exist_ok=True)

    train_transforms = Compose([
        RandomHorizontalFlip(prob=0.5),
        ToTensor(),
    ])
    val_transforms = Compose([ToTensor()])

    train_dataset = InvoiceDataset(
        os.path.join(DATA_DIR, "images", "train"),
        os.path.join(DATA_DIR, "annotations", "train"),
        transforms=train_transforms,
    )
    val_dataset = InvoiceDataset(
        os.path.join(DATA_DIR, "images", "val"),
        os.path.join(DATA_DIR, "annotations", "val"),
        transforms=val_transforms,
    )

    train_loader = DataLoader(
        train_dataset, batch_size=4, shuffle=True,
        num_workers=0, collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=1, shuffle=False,
        num_workers=0, collate_fn=collate_fn,
    )

    device = torch.device('cpu')
    print(f"使用设备: {device}")

    print("正在加载预训练模型...")
    weights = FasterRCNN_ResNet50_FPN_Weights.DEFAULT
    model = fasterrcnn_resnet50_fpn(weights=weights)

    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, len(CLASS_NAMES))

    model.to(device)
    print("模型加载完成（COCO 预训练 + 自定义分类头）")

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.SGD(params, lr=0.005, momentum=0.9, weight_decay=0.0005)
    lr_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=200, eta_min=1e-6)

    epochs = 200
    best_map50 = 0.0
    patience = 30
    no_improve_count = 0

    train_losses = {'total': [], 'box_reg': [], 'classifier': [], 'rpn_box': [], 'rpn_obj': []}
    val_losses = {'total': [], 'box_reg': [], 'classifier': [], 'rpn_box': [], 'rpn_obj': []}
    val_metrics = {'precision': [], 'recall': [], 'map50': [], 'map50_95': []}
    epoch_lrs = []

    csv_path = os.path.join(MODEL_SAVE, "training_log.csv")

    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['epoch', 'train_loss', 'val_loss', 'precision', 'recall', 'mAP50', 'mAP50-95', 'lr'])

        for epoch in range(epochs):
            model.train()
            epoch_loss = {'total': 0, 'box_reg': 0, 'classifier': 0, 'rpn_box': 0, 'rpn_obj': 0}
            batch_count = 0

            for i, (images, targets) in enumerate(train_loader):
                images = [img.to(device) for img in images]
                targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

                loss_dict = model(images, targets)
                losses = sum(loss for loss in loss_dict.values())

                if torch.isnan(losses):
                    print(f"  [警告] Epoch {epoch+1} 出现 nan，跳过本批次")
                    continue

                optimizer.zero_grad()
                losses.backward()
                torch.nn.utils.clip_grad_norm_(params, max_norm=1.0)
                optimizer.step()

                for key in epoch_loss:
                    if key == 'total':
                        epoch_loss[key] += losses.item()
                    elif key == 'box_reg':
                        epoch_loss[key] += loss_dict.get('loss_box_reg', torch.tensor(0.0)).item()
                    elif key == 'classifier':
                        epoch_loss[key] += loss_dict.get('loss_classifier', torch.tensor(0.0)).item()
                    elif key == 'rpn_box':
                        epoch_loss[key] += loss_dict.get('loss_rpn_box_reg', torch.tensor(0.0)).item()
                    elif key == 'rpn_obj':
                        epoch_loss[key] += loss_dict.get('loss_rpn_objectness', torch.tensor(0.0)).item()
                batch_count += 1

                if (i + 1) % 5 == 0 or (i + 1) == len(train_loader):
                    print(f"  Epoch {epoch+1} [{i+1}/{len(train_loader)}] loss: {losses.item():.4f}")

            lr_scheduler.step()
            current_lr = optimizer.param_groups[0]['lr']

            for key in train_losses:
                train_losses[key].append(epoch_loss[key] / max(batch_count, 1))
            epoch_lrs.append(current_lr)

            model.eval()
            val_loss = {'total': 0, 'box_reg': 0, 'classifier': 0, 'rpn_box': 0, 'rpn_obj': 0}
            val_batch = 0
            val_predictions = []
            val_targets = []

            with torch.no_grad():
                model.train()
                for images, targets in val_loader:
                    images = [img.to(device) for img in images]
                    targets_cpu = [{k: v.cpu() for k, v in t.items()} for t in targets]
                    targets_dev = [{k: v.to(device) for k, v in t.items()} for t in targets]

                    loss_dict = model(images, targets_dev)
                    losses = sum(loss for loss in loss_dict.values())

                    for key in val_loss:
                        if key == 'total':
                            val_loss[key] += losses.item()
                        elif key == 'box_reg':
                            val_loss[key] += loss_dict.get('loss_box_reg', torch.tensor(0.0)).item()
                        elif key == 'classifier':
                            val_loss[key] += loss_dict.get('loss_classifier', torch.tensor(0.0)).item()
                        elif key == 'rpn_box':
                            val_loss[key] += loss_dict.get('loss_rpn_box_reg', torch.tensor(0.0)).item()
                        elif key == 'rpn_obj':
                            val_loss[key] += loss_dict.get('loss_rpn_objectness', torch.tensor(0.0)).item()
                    val_batch += 1

                model.eval()
                for images, targets in val_loader:
                    images = [img.to(device) for img in images]
                    targets_cpu = [{k: v.cpu() for k, v in t.items()} for t in targets]

                    preds = model(images)
                    val_predictions.extend(preds)
                    val_targets.extend(targets_cpu)

            for key in val_losses:
                val_losses[key].append(val_loss[key] / max(val_batch, 1))

            precision, recall, map50 = compute_map_at_iou(val_predictions, val_targets, iou_threshold=0.5)
            _, _, map50_95 = compute_map_at_iou(val_predictions, val_targets, iou_threshold=0.75)

            val_metrics['precision'].append(precision)
            val_metrics['recall'].append(recall)
            val_metrics['map50'].append(map50)
            val_metrics['map50_95'].append(map50_95)

            avg_train_loss = train_losses['total'][-1]
            avg_val_loss = val_losses['total'][-1]

            writer.writerow([
                epoch + 1, f"{avg_train_loss:.6f}", f"{avg_val_loss:.6f}",
                f"{precision:.4f}", f"{recall:.4f}", f"{map50:.4f}", f"{map50_95:.4f}",
                f"{current_lr:.6f}"
            ])

            print(f"Epoch {epoch+1}/{epochs} - Train: {avg_train_loss:.4f} | Val: {avg_val_loss:.4f} | "
                  f"P: {precision:.3f} R: {recall:.3f} mAP50: {map50:.3f} mAP50-95: {map50_95:.3f} | LR: {current_lr:.6f}")

            if map50 > best_map50:
                best_map50 = map50
                torch.save(model.state_dict(), os.path.join(MODEL_SAVE, "best.pth"))
                no_improve_count = 0
                print(f"  -> 保存最佳模型 (mAP50: {best_map50:.4f})")
            else:
                no_improve_count += 1
                if no_improve_count >= patience:
                    print(f"\n早停触发：mAP50 连续 {patience} 轮未提升，停止训练")
                    break

        torch.save(model.state_dict(), os.path.join(MODEL_SAVE, "last.pth"))

    print(f"\n训练完成！最佳 mAP50: {best_map50:.4f}，模型保存在: {MODEL_SAVE}/best.pth")

    plot_training_curves(train_losses, val_losses, val_metrics, epoch_lrs, MODEL_SAVE)


def plot_training_curves(train_losses, val_losses, val_metrics, epoch_lrs, save_dir):
    epochs_range = range(1, len(epoch_lrs) + 1)

    fig, axes = plt.subplots(2, 5, figsize=(20, 8))

    def smooth(data, alpha=0.3):
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(alpha * data[i] + (1 - alpha) * result[-1])
        return result

    axes[0, 0].plot(epochs_range, train_losses['box_reg'], 'b.-', markersize=3, label='results')
    axes[0, 0].plot(epochs_range, smooth(train_losses['box_reg']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[0, 0].set_title('train/box_loss')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(epochs_range, train_losses['classifier'], 'b.-', markersize=3, label='results')
    axes[0, 1].plot(epochs_range, smooth(train_losses['classifier']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[0, 1].set_title('train/cls_loss')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)

    axes[0, 2].plot(epochs_range, train_losses['rpn_box'], 'b.-', markersize=3, label='results')
    axes[0, 2].plot(epochs_range, smooth(train_losses['rpn_box']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[0, 2].set_title('train/dfi_loss')
    axes[0, 2].set_xlabel('Epoch')
    axes[0, 2].legend()
    axes[0, 2].grid(True, alpha=0.3)

    axes[0, 3].plot(epochs_range, val_metrics['precision'], 'b.-', markersize=3, label='results')
    axes[0, 3].plot(epochs_range, smooth(val_metrics['precision']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[0, 3].set_title('metrics/precision(B)')
    axes[0, 3].set_xlabel('Epoch')
    axes[0, 3].set_ylim(0, 1.05)
    axes[0, 3].legend()
    axes[0, 3].grid(True, alpha=0.3)

    axes[0, 4].plot(epochs_range, val_metrics['recall'], 'b.-', markersize=3, label='results')
    axes[0, 4].plot(epochs_range, smooth(val_metrics['recall']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[0, 4].set_title('metrics/recall(B)')
    axes[0, 4].set_xlabel('Epoch')
    axes[0, 4].set_ylim(0, 1.05)
    axes[0, 4].legend()
    axes[0, 4].grid(True, alpha=0.3)

    axes[1, 0].plot(epochs_range, val_losses['box_reg'], 'b.-', markersize=3, label='results')
    axes[1, 0].plot(epochs_range, smooth(val_losses['box_reg']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[1, 0].set_title('val/box_loss')
    axes[1, 0].set_xlabel('Epoch')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(epochs_range, val_losses['classifier'], 'b.-', markersize=3, label='results')
    axes[1, 1].plot(epochs_range, smooth(val_losses['classifier']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[1, 1].set_title('val/cls_loss')
    axes[1, 1].set_xlabel('Epoch')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    axes[1, 2].plot(epochs_range, val_losses['rpn_box'], 'b.-', markersize=3, label='results')
    axes[1, 2].plot(epochs_range, smooth(val_losses['rpn_box']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[1, 2].set_title('val/dfi_loss')
    axes[1, 2].set_xlabel('Epoch')
    axes[1, 2].legend()
    axes[1, 2].grid(True, alpha=0.3)

    axes[1, 3].plot(epochs_range, val_metrics['map50'], 'b.-', markersize=3, label='results')
    axes[1, 3].plot(epochs_range, smooth(val_metrics['map50']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[1, 3].set_title('metrics/mAP50(B)')
    axes[1, 3].set_xlabel('Epoch')
    axes[1, 3].set_ylim(0, 1.05)
    axes[1, 3].legend()
    axes[1, 3].grid(True, alpha=0.3)

    axes[1, 4].plot(epochs_range, val_metrics['map50_95'], 'b.-', markersize=3, label='results')
    axes[1, 4].plot(epochs_range, smooth(val_metrics['map50_95']), color='orange', linestyle=':', linewidth=1.5, label='smooth')
    axes[1, 4].set_title('metrics/mAP50-95(B)')
    axes[1, 4].set_xlabel('Epoch')
    axes[1, 4].set_ylim(0, 1.05)
    axes[1, 4].legend()
    axes[1, 4].grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = os.path.join(save_dir, "results.png")
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"训练结果图已保存: {save_path}")


if __name__ == '__main__':
    main()
