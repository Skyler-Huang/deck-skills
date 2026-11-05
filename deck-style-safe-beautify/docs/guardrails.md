# 零改动护栏与校验清单

「保风格美化」的全部技术难度都在一件事上：**只加一层，其余一个字节都不动**。本文定义这层护栏由哪些机制保证，以及怎么证明它成立。

---

## 一、允许的改动（白名单）

| 改动 | 载体 | 约束 |
|---|---|---|
| 每页 1 张全页装饰图 | `p:pic`，`spTree` 中位于第一个原有形状之后 | 恰好 1 张；全页尺寸；名称带统一前缀 |
| 切换动效（可选） | `p:transition` | 必须在 `clrMapOvr` 之后、`timing` 之前；不生成 `p:timing` |
| 以上之外 | **一律不允许** | 包括 `p:bg`、形状属性、文字、文件名 |

任何不在白名单里的改动，都要先回到 `SKILL.md` 第 0 步重新确认范围。

---

## 二、八条硬护栏

### 1. 渐变底板逐字一致

原稿的底板通常是一个名为 `deco_bg` 的全页矩形，带 `a:gradFill`。**不要**改成 `noFill`，**不要**替换色值，**不要**改角度。校验方式：

```python
etree.tostring(orig.shapes[0]._element.spPr) == etree.tostring(final.shapes[0]._element.spPr)
```

注意比较的是 `spPr` 的**序列化字节**，不是"看起来一样"。

### 2. 不设页面级背景

`p:cSld/p:bg` 一旦出现，说明你把用户的背景设置换掉了。校验：

```python
slide._element.find(ns + "cSld/" + ns + "bg") is None
```

装饰必须作为**普通的 `p:pic` 形状**插入，而不是页面背景。

### 3. 层级：装饰在渐变之上、内容之下

`spTree` 的 children 前两个是 `p:nvGrpSpPr`、`p:grpSpPr`，之后才是可视形状。所以「`shapes` 序列 index 1」对应 `spTree` 中「第一个原有形状之后」。

```python
pic = slide.shapes.add_picture(path, 0, 0, width=W, height=H)
sp_tree = slide.shapes._spTree
first = list(slide.shapes)[0]._element      # add_picture 后 [0] 仍是原渐变底板
idx = list(sp_tree).index(first)
el = pic._element
sp_tree.remove(el)
sp_tree.insert(idx + 1, el)
```

**为什么必须是这个位置**：白底卡片是不透明的，会自然盖住装饰；装饰只从卡片之外的四角露出来。若放在最顶层，就会盖住文字和卡片 —— 这是最常见的层级错误。

### 4. 从原稿重新装配，不替换 media

成品里多个页面可能共用同一张 `ppt/media/imageN.jpg`（同一个 `r:embed`）。按页替换媒体文件会**连坐其它页**。`apply_background.py` 检测到输入已含装饰层前缀就直接报错：

```
第 N 页已存在 aigc_bg_ 装饰层。请从原稿重新装配，
不要在成品上替换 ppt/media/（多页可能共用同一张图）
```

### 5. 中部正文区数学上零干扰

`make_background.py` 的 `center_fade(clear=0.22, feather=0.06)` 生成一个「中部为 0、边缘为 1」的掩码，装饰层 alpha 在合成前乘以它：

```python
a = np.array(dec.getchannel("A")).astype(float)
dec.putalpha(Image.fromarray((a * fade[:, :, 0]).astype("uint8"), "L"))
```

这不是"调淡一点"，是让中部装饰强度**恒等于 0**。校验时用渲染图算中部差异，而不是看装饰图本身。

### 6. 原有动画只保留、不手写

原稿常有 `p:timing`（逐条出现动画）。手写动画 XML 极易让 PowerPoint 提示「需要修复」。本技能只加 `p:transition`（切换），并且：

- 用 `etree` 解析后只操作根节点下的 `p:transition`；
- 比对注入前后 `p:timing` 的序列化字节，必须完全相同；
- `p:transition` 顺序为 `cSld → clrMapOvr → transition → timing → extLst`，顺序错了也会触发修复。

### 7. 文件名不变

交付文件名必须与输入一致。上传文件常带系统前缀（如 `<上传前缀>-教学产品-<学校>-<姓名>-<作品名>.pptx`），这是输入本身带的，不算改名；但**不要把它改成"美化版""final"之类**。

`verify_zero_change.py` 把这一项列为「人工确认」，因为另存新版有时是合理的 —— 但必须明确告知用户。

### 8. 用户自带图片完整保留

如果原稿某页已有产品界面截图、图表、logo，装饰层在它之下，不能覆盖它。校验：原有 `p:pic` 数量与图片字节完全一致。

---

## 三、校验矩阵

`verify_zero_change.py` 输出这张表。**全部 PASS 才算完成**：

| 检查项 | 期望 | 失败含义 |
|---|---|---|
| 页数一致 | N / N | 装配时丢了页 |
| 渐变底板 `spPr` XML 逐字一致 | N / N | 背景风格被改 |
| 渐变底板未被改成 `noFill` | 0 | 用"透明化底板"偷换了背景 |
| 新增页面级背景图 `p:bg` | 0 | 换了页面背景设置 |
| 装饰层每页恰好 1 张且位于第 2 位 | N / N | 层级错误或重复装配 |
| 原有形状数量变化页 | 0 | 原有对象被增删 |
| 文字内容变化页 | 0 | 文案被改 |
| 形状签名全等页 | N / N | 位置/尺寸/渐变/填充/透明度/文字有改动 |
| 原有图片完整保留 | 0 处差异 | 覆盖了用户自带截图 |
| 原有 `p:timing` 完整保留 | N / N | 动画被破坏 |
| `p:transition` 位置合法 | N / N | 顺序错，PowerPoint 可能提示修复 |
| 文件名 | 与输入一致 | 违反铁律 2 |
| 中部正文区渲染差异 | < 3.0 | 装饰干扰正文 |
| 中部差异 > 15 的像素占比 | < 0.01% | 有可见物压在正文上 |
| 四周边缘带渲染差异 | > 0.3 | **美化淡到看不见**，等于没做 |

**形状签名**包含：left/top/width/height（英寸，4 位小数）、rotation、渐变 stops 与角度、纯色填充、透明度、文字全文。

---

## 四、为什么必须用独立渲染做视觉校验

内置截图工具可能对同一文件路径缓存旧版本 —— 实测连「新增一张纯红不透明矩形」都返回原稿像素，导致你误以为代码没生效或层级没错。

可靠路径：

```bash
soffice --headless --convert-to pdf --outdir /tmp/r /tmp/<新文件名>.pptx
pdftoppm -f N -l N -r 100 -png -singlefile /tmp/r/<新文件名>.pdf /tmp/r/pN
```

- 每次验证用**新的临时文件名**；
- 原稿与成品用**同样的 DPI 和页码集合**渲染，才能逐像素相减；
- `render_deck.py` 已封装这一步。

---

## 五、校验之后仍要人工看一眼

自动化只能证明"没改坏"，不能证明"好看"。至少看 3 张：

1. **封面**：主视觉（放大镜/标题/卡片）完整、装饰没抢戏；
2. **一页内容密集的内页**：四角装饰明显、正文清晰；
3. **用户自带截图那一页**：截图完整、无遮挡。

以及一张「原稿 vs 美化」并排对比图 —— 这是用户判断"美化看得出来吗"的唯一依据，务必提供。
