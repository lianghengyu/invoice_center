import os
import csv
import torch
from torch.utils.data import Dataset
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.transforms import functional as F
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


class InvoiceDataset(Dataset):
    def __init__(self, img_dir, ann_dir):
        self.img_dir = img_dir
        self.ann_dir = ann_dir
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

        img_tensor = F.to_tensor(img)

        return img_tensor, target


def collate_fn(batch):
    return tuple(zip(*batch))


def main():
    os.makedirs(MODEL_SAVE, exist_ok=True)

    train_dataset = InvoiceDataset(
        os.path.join(DATA_DIR, "images", "train"),
        os.path.join(DATA_DIR, "annotations", "train"),
    )
    val_dataset = InvoiceDataset(
        os.path.join(DATA_DIR, "images", "val"),
        os.path.join(DATA_DIR, "annotations", "val"),
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

    print("正在加载模型...")
    model = fasterrcnn_resnet50_fpn(weights=None, num_classes=len(CLASS_NAMES))
    print("模型加载完成")
    model.to(device)

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.SGD(params, lr=0.001, momentum=0.9, weight_decay=0.0005)
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)

    epochs = 100
    best_loss = float('inf')

    epoch_losses = []
    epoch_lrs = []
    csv_path = os.path.join(MODEL_SAVE, "training_log.csv")

    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['epoch', 'avg_loss', 'best_loss', 'lr'])

        for epoch in range(epochs):
            model.train()
            epoch_loss = 0

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

                epoch_loss += losses.item()

                if (i + 1) % 5 == 0 or (i + 1) == len(train_loader):
                    print(f"  Epoch {epoch+1} [{i+1}/{len(train_loader)}] batch_loss: {losses.item():.4f}")

            lr_scheduler.step()
            avg_loss = epoch_loss / len(train_loader)
            current_lr = optimizer.param_groups[0]['lr']

            epoch_losses.append(avg_loss)
            epoch_lrs.append(current_lr)

            writer.writerow([epoch + 1, f"{avg_loss:.6f}", f"{best_loss:.6f}", f"{current_lr:.6f}"])

            print(f"Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.4f} - LR: {current_lr:.6f}")

            if avg_loss < best_loss:
                best_loss = avg_loss
                torch.save(model.state_dict(), os.path.join(MODEL_SAVE, "best.pth"))
                print(f"  -> 保存最佳模型 (loss: {best_loss:.4f})")

        torch.save(model.state_dict(), os.path.join(MODEL_SAVE, "last.pth"))

    print(f"\n训练完成！模型保存在: {MODEL_SAVE}/best.pth")

    plot_training_curves(epoch_losses, epoch_lrs, MODEL_SAVE)


def plot_training_curves(epoch_losses, epoch_lrs, save_dir):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    ax1.plot(range(1, len(epoch_losses) + 1), epoch_losses, 'b-', linewidth=1.5)
    ax1.set_xlabel('Epoch')
    ax1.set_ylabel('Average Loss')
    ax1.set_title('Faster R-CNN Training Loss Curve')
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(1, len(epoch_losses))

    best_idx = epoch_losses.index(min(epoch_losses)) + 1
    ax1.axvline(x=best_idx, color='r', linestyle='--', label=f'Best: Epoch {best_idx} ({min(epoch_losses):.4f})')
    ax1.legend()

    ax2.plot(range(1, len(epoch_lrs) + 1), epoch_lrs, 'g-', linewidth=1.5)
    ax2.set_xlabel('Epoch')
    ax2.set_ylabel('Learning Rate')
    ax2.set_title('Learning Rate Schedule')
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')

    plt.tight_layout()
    save_path = os.path.join(save_dir, "training_curves.png")
    plt.savefig(save_path, dpi=150)
    plt.close()
    print(f"训练曲线已保存: {save_path}")


if __name__ == '__main__':
    main()
