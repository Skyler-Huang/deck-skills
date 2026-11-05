#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_deck.py — 用 LibreOffice 独立渲染 PPTX 为逐页 PNG。

为什么需要它：某些内置截图工具对同一文件路径缓存旧版本，会把「新增的
纯红矩形」也渲染成原稿像素，导致视觉验证完全失效。本脚本每次把文件复制成
唯一临时名，走 soffice -> PDF -> pdftoppm，结果可复现、不受缓存影响。

用法:
  python3 render_deck.py deck.pptx --out pages/
  python3 render_deck.py deck.pptx --out pages/ --pages 1,5,12,20 --dpi 120
  python3 render_deck.py deck.pptx --out pages/ --keep-pdf
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile


def check_tools():
    missing = [t for t in ("soffice", "pdftoppm") if shutil.which(t) is None]
    if missing:
        print("缺少依赖: {} | Ubuntu: apt install libreoffice-impress poppler-utils".format(
            ", ".join(missing)), file=sys.stderr)
        return False
    return True


def render(pptx, out_dir, pages=None, dpi=100, keep_pdf=False, timeout=300):
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="deckrender_")
    try:
        # 唯一文件名：绕开渲染服务对路径的缓存
        work = os.path.join(tmp, "render_" + os.path.basename(pptx))
        shutil.copy2(pptx, work)
        env = dict(os.environ)
        env["HOME"] = tmp  # 避免 soffice 用户配置串扰
        cmd = ["soffice", "--headless", "--norestore",
               "--convert-to", "pdf", "--outdir", tmp, work]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        pdfs = glob.glob(os.path.join(tmp, "*.pdf"))
        if not pdfs:
            raise RuntimeError("LibreOffice 未能生成 PDF: " + (r.stdout + r.stderr)[-400:])
        pdf = pdfs[0]
        if keep_pdf:
            shutil.copy2(pdf, os.path.join(out_dir, "render.pdf"))

        if pages:
            wanted = [int(x) for x in pages.split(",") if x.strip().isdigit()]
        else:
            # 用 pdfinfo 拿页数，失败则从 1 递增直到不再产出
            try:
                info = subprocess.run(["pdfinfo", pdf], capture_output=True,
                                      text=True, timeout=30)
                n = 1
                for line in info.stdout.splitlines():
                    if line.lower().startswith("pages:"):
                        n = int(line.split(":", 1)[1].strip())
                wanted = list(range(1, n + 1))
            except Exception:
                wanted = list(range(1, 100))

        made = []
        for p in wanted:
            dst = os.path.join(out_dir, "p{}".format(p))
            c = ["pdftoppm", "-f", str(p), "-l", str(p), "-r", str(dpi),
                 "-png", "-singlefile", pdf, dst]
            rr = subprocess.run(c, capture_output=True, text=True, timeout=120)
            f = dst + ".png"
            if os.path.isfile(f):
                made.append(f)
            elif rr.returncode != 0 and not pages:
                break  # 已到末页
        return made
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="LibreOffice 独立渲染 PPTX 为逐页 PNG")
    ap.add_argument("pptx", help="输入 .pptx")
    ap.add_argument("--out", required=True, help="PNG 输出目录")
    ap.add_argument("--pages", help="只渲染指定页，如 1,5,12；缺省渲染全部")
    ap.add_argument("--dpi", type=int, default=100, help="渲染 DPI（默认 100）")
    ap.add_argument("--keep-pdf", action="store_true", help="同时保留渲染出的 PDF")
    ap.add_argument("--timeout", type=int, default=300, help="PDF 转换超时秒数")
    args = ap.parse_args()

    if not os.path.isfile(args.pptx):
        print("找不到文件: " + args.pptx, file=sys.stderr)
        return 2
    if not check_tools():
        return 3
    files = render(args.pptx, args.out, args.pages, args.dpi,
                   args.keep_pdf, args.timeout)
    print("已渲染 {} 页 -> {}".format(len(files), args.out))
    for f in files[:5]:
        print("  " + f)
    if len(files) > 5:
        print("  ...")
    return 0 if files else 1


if __name__ == "__main__":
    sys.exit(main())
