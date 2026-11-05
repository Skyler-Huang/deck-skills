# OOXML 操作笔记

只需要懂这几处就够写装配与动效代码。**改错了会让 PowerPoint 提示「需要修复」**，所以每一步都给可验证的判定。

---

## 1. `.pptx` 就是一个 zip

```
ppt/
  presentation.xml
  slides/slide1.xml … slideN.xml          ← 每页内容
  slides/_rels/slideN.xml.rels            ← 图片/版式的关系映射
  media/image1.jpg …                     ← 图片二进制
  slideLayouts/, slideMasters/, theme/
[Content_Types].xml
```

用 `zipfile` 改写单个 XML 时，**必须把全部条目读进内存 → 写临时文件 → `os.replace()`**。不要对同一路径同时开读和写（`ZipFile(path,"w")` 一打开就截断源文件，实测直接把 PPT 写坏）。

```python
with zipfile.ZipFile(path) as z:
    infos = z.infolist()
    blobs = {i.filename: z.read(i.filename) for i in infos}
tmp = path + ".tmp"
with zipfile.ZipFile(tmp, "w") as zout:
    for info in infos:
        zout.writestr(info, changed.get(info.filename, blobs[info.filename]))
os.replace(tmp, path)
```

`writestr(info, data)` 复用原 `ZipInfo`，能保留压缩方式与时间戳。

---

## 2. `CT_Slide` 子元素顺序（写死，不能乱）

```xml
<p:sld>
  <p:cSld> ... </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
  <p:transition spd="slow" advClick="1"><p:fade/></p:transition>   <!-- 可选 -->
  <p:timing> ... </p:timing>                                        <!-- 可选 -->
  <p:extLst> ... </p:extLst>                                        <!-- 可选 -->
</p:sld>
```

`p:transition` 必须插在 `clrMapOvr` 之后、`timing` 之前。若原稿没有 `clrMapOvr`（可选元素），就插在 `cSld` 之后。

`p:timing` 是**进入动画序列**（逐条出现、淡入等），原稿常自带。手写它风险极高：节点 id、时序树、`p:cBhvr`/`p:tgtEl` 引用错一处就会触发修复。本技能只加 `p:transition`，`p:timing` 原样保留。

> 注意：`p:timing` 里常有 `<p:animEffect transition="in" filter="fade">` 这样的**属性**。用 `'transition' in xml` 判断有没有残留切换会得到误报，必须按命名空间找 `p:transition` **元素**。

---

## 3. `spTree` 与形状层级

```xml
<p:cSld>
  <p:spTree>
    <p:nvGrpSpPr>...</p:nvGrpSpPr>      <!-- 非可视 -->
    <p:grpSpPr>...</p:grpSpPr>          <!-- 非可视 -->
    <p:sp>  ... deco_bg 渐变底板 ... </p:sp>   ← shapes[0]
    <p:sp>  ... 卡片 / 文字 ... </p:sp>         ← shapes[1..]
    ...
  </p:spTree>
</p:cSld>
```

`python-pptx` 的 `slide.shapes` 只包含可视元素（`p:sp` / `p:pic` / `p:graphicFrame` / `p:grpSp` / `p:cxnSp`），顺序即 z-order（后面的盖前面的）。

要让装饰层在渐变底板之上、所有内容之下，就放到 `shapes` 序列 **index 1**：

```python
pic = slide.shapes.add_picture(path, 0, 0, width=W, height=H)  # 默认 append 到末尾
sp_tree = slide.shapes._spTree
first = list(slide.shapes)[0]._element
idx = list(sp_tree).index(first)
el = pic._element
sp_tree.remove(el)
sp_tree.insert(idx + 1, el)
```

**不要**用 `sp_tree.insert(1, el)` —— 那是插到 `nvGrpSpPr` 与 `grpSpPr` 之间，会破坏结构。

---

## 4. `p:pic` 与图片关系

```xml
<p:pic>
  <p:nvPicPr>
    <p:cNvPr id="..." name="aigc_bg_01"/>   <!-- 校验脚本按 name 前缀识别 -->
    <p:cNvPicPr/><p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="rId2"/>
    <a:stretch><a:fillRect/></a:stretch>
  </p:blipFill>
  <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="..." cy="..."/></a:xfrm>
          <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>
```

`slideN.xml.rels` 里：

```xml
<Relationship Id="rId2" Type=".../image" Target="../media/image3.jpg"/>
```

要点：

- `python-pptx` 的 `add_picture()` 会自动创建 rel 并**对完全相同的图片字节去重**（多个页面可能共用同一个 `rId`）。这正是「不要按页替换 media」的原因。
- 改图片名请用 `pic._element.nvPicPr.cNvPr.set("name", ...)`，不要依赖 `shape.name` 的 setter（版本差异）。
- 全页尺寸用 `prs.slide_width` / `prs.slide_height`（EMU），`left=top=0`。

---

## 5. 页面级背景 `p:bg` 为什么不能用

```xml
<p:cSld><p:bg><p:bgPr>...</p:bgPr></p:bg> ... </p:cSld>
```

一旦设置，就等于替换了用户的背景设置，而且它会在所有形状之下 —— 你连"渐变底板"这一层都绕过去了。更糟的是某些渲染器对图片型 `p:bg` 支持不一致。

**装饰永远是普通的 `p:pic` 形状**，不是页面背景。`verify_zero_change.py` 会检查 `p:bg` 数量为 0。

---

## 6. 渐变底板 `a:gradFill`

```xml
<a:gradFill rotWithShape="1">
  <a:gsLst>
    <a:gs pos="0"><a:srgbClr val="BFE9FF"/></a:gs>
    <a:gs pos="100000"><a:srgbClr val="FFFDF0"/></a:gs>
  </a:gsLst>
  <a:lin ang="5400000" scaled="1"/>   <!-- 5400000 = 90° = 上到下 -->
</a:gradFill>
```

`ang` 单位是 1/60000 度。`inspect_deck.py` 会换算成 `angle_deg` 写进 tokens。校验时**直接比对 `<p:spPr>` 的序列化字节**，而不是逐个属性比 —— 前者能捕获任何细微改动。

---

## 7. `p:transition` 可用片段

```xml
<!-- 柔和淡入（默认） -->
<p:transition spd="slow" advClick="1"><p:fade/></p:transition>

<!-- 推近，章节入口用 -->
<p:transition spd="slow" advClick="1"><p:zoom dir="in"/></p:transition>
```

`spd` 取值 `slow | med | fast`；`advClick="1"` 表示单击换片。不要设 `advTm`（自动换片时间），不要加 `p:sndAc`（声音）。

`CT_SlideTransition` 的可选子元素还有 `p:push` / `p:wipe` / `p:blinds` / `p:checker` / `p:cut` 等，但越花哨越违背「克制」原则。

---

## 8. 常见命名空间

```python
P  = "http://schemas.openxmlformats.org/presentationml/2006/main"   # p:
A  = "http://schemas.openxmlformats.org/drawingml/2006/main"         # a:
R  = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"  # r:
```

用 `lxml` 时写成 `"{%s}tag" % NS`；`python-pptx` 的元素还支持 `.xpath("./p:nvPicPr/p:cNvPr")`（内置命名空间映射，不用传 `namespaces`）。

---

## 9. 合法性自检

```bash
# XML 合法 + 渲染器能打开
soffice --headless --convert-to pdf --outdir /tmp/r /tmp/deck.pptx

# 结构校验
python3 scripts/verify_zero_change.py ORIG.pptx deck.pptx \
    --prefix aigc_bg_ --report check.md
```

LibreOffice 能成功转 PDF，基本可以确认 OOXML 结构合法、顺序正确。但**这不等于微软 PowerPoint / WPS 一定兼容** —— 手写 XML 的兼容边界只能由用户在实际演示软件里确认，交付时要如实说明。
