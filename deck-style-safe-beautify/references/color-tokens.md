# 色板令牌（color tokens）

所有绘制脚本唯一读取 `assets/color-tokens.json`（或你指定的路径）。**不要凭肉眼猜十六进制，不要在脚本里硬编码颜色。**

---

## 一、Schema

```json
{
  "background": {
    "type": "linear-gradient",
    "top": "BFE9FF",
    "bottom": "FFFDF0",
    "angle_deg": 90.0
  },
  "ink": "3F6478",
  "accents": ["FFD23F", "FF5D8F", "2EC4E6", "7BD389", "FF6B35"],
  "source_palette": ["3F6478", "17384D", "FFFFFF", "..."],
  "note": "..."
}
```

| 字段 | 含义 | 被谁使用 |
|---|---|---|
| `background.top` / `bottom` | 渐变起止色，6 位十六进制（可带或不带 `#`） | `make_background.gradient()` |
| `background.angle_deg` | 90 = 上→下；0 = 左→右 | `make_background.gradient()` |
| `ink` | 主文字/描边墨色 | `Palette.ink`、卡片描边、投影 |
| `accents` | **装饰强调色，顺序有意义** | 四角星、贴纸、高亮笔触 |
| `source_palette` | 原稿里出现的全部颜色（备查，不直接用于绘制） | 人工复核 |

纯色底：把 `top` 与 `bottom` 填成同一个值。

---

## 二、生成方式

```bash
python3 scripts/inspect_deck.py INPUT.pptx \
    --out inspect.json --tokens assets/color-tokens.json
```

`inspect_deck.py` 会：

1. 找到首页的全页底板形状（`deco_bg`），解析 `a:gradFill` 的 `a:gs` 色标与 `a:lin/@ang`；
2. 统计全稿 `a:srgbClr` 的颜色频次，得到 `source_palette`；
3. 把已知品牌亮色按固定顺序（黄 → 粉 → 青 → 绿 → 橙 → 紫）提到 `accents` 前面，其余按色度补充，并剔除底色、纯白、纯黑与 `ink`。

---

## 三、必须人工复核（最容易出错的一步）

### 1. `accents` 的顺序

`decor_recipe.py` 画四角星时用 `rnd.choice(pal.accents)`，并取 `accents[0..3]` 作为 yellow/pink/cyan/green。如果第一位是墨蓝或深灰，**星星会画成暗色，整份 PPT 立刻变沉**。

早期版本按颜色出现频次排序，就把 `3F6478`（墨蓝）顶到了第一位。现已修正为品牌亮色优先，但仍要打开 JSON 看一眼，按项目 CSS 的顺序调整。

### 2. 项目有锁定色板时，以项目为准

真实案例里项目 `app.css` / 机制图脚本明确给出：

```
INK    #17384d    SKY    #bfe9ff    ORANGE #ff6b35
YELLOW #ffd23f    PINK   #ff5d8f    PURPLE #a06cd5
SOFT   #3f6478    GREEN  #7bd389
```

这种情况下**直接把这些值写进 tokens**，比从 PPT 里频次统计更准 —— 因为 PPT 可能只用了其中一部分。`source_palette` 保留备查即可。

### 3. 找不到渐变底板时

`inspect.json` 里 `base_shape` 为 `null`，tokens 会退回内置示例色板 `BFE9FF / FFFDF0`。**此时严禁直接继续** —— 那等于给用户的 PPT 换了一套底色。手工从原稿渲染图取色，或读项目的 CSS 变量，把真实值填进去。

### 4. 主题色 / scheme 色

若渐变色标是 `scheme:accent1` 这类引用而非 `srgbClr`，`inspect_deck.py` 会跳过它。需要去 `ppt/theme/theme1.xml` 解析实际色值后手工填入。

---

## 四、验证色板是否锁对

```bash
python3 scripts/make_background.py --tokens assets/color-tokens.json \
    --pages 1 --out /tmp/bgcheck/ --size 1600x900
python3 - <<'PY'
from PIL import Image
im = Image.open('/tmp/bgcheck/bg_01.jpg').convert('RGB')
print('top   ', im.getpixel((800, 5)))     # 应≈ (191,233,255)
print('bottom', im.getpixel((800, 895)))   # 应≈ (255,253,240)
PY
```

顶部/底部像素应与 tokens 的 RGB 值几乎完全一致（JPEG 压缩会有 ±2 误差）。差得远就是色板错了。

---

## 五、本包的示例色板

见 `assets/color-tokens.example.json`。它是从一份「浅蓝→暖白 + 墨蓝 + 四角星」的真实路演稿提取的，仅作格式示例 —— **换一份 PPT 必须重新提取**，不要直接复用。
