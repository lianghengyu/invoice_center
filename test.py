import cv2
import numpy as np
import sys

# 用你实际的发票图片路径替换
img = cv2.imread(r'C:/Users/QIN/Desktop/001.png')
if img is None:
    print("无法读取图片，请检查路径")
    sys.exit(1)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 50, 150, apertureSize=3)
lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                        minLineLength=100, maxLineGap=10)

print("lines is None:", lines is None)
if lines is not None:
    print("lines shape:", lines.shape)
    print("lines dtype:", lines.dtype)
    print("第一条 line:", lines[0])
    print("第一条 line 的类型:", type(lines[0]))
    if lines[0].ndim == 1:
        print("line[0]:", lines[0][0], "  ← 这是一个标量，无法解包！")
    elif lines[0].ndim == 2:
        print("line[0]:", lines[0][0], "  ← 这是数组，可以解包")