#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
build_tech.py —— 把 Markdown 笔记批量转换成「技术分享」文章页，并同步更新文章列表

它解决的问题：
  以前每写一篇笔记，要手工复制一份 HTML、改标题、改日期，再到 tech 和首页各加一张卡片。
  现在笔记目录就是唯一数据源，改完笔记跑一条命令，页面和列表全部重生成。

用法：
    python3 scripts/build_tech.py             # 生成 / 更新
    python3 scripts/build_tech.py --dry-run   # 只打印会做哪些事，不写文件
    python3 scripts/build_tech.py --src 某目录 # 临时只处理指定目录（可多次指定）

新增文章：
    把 .md 丢进下面 SOURCES 里任何一个目录即可，再跑一次脚本；
    SOURCES 的 root 也可以直接指向单个 .md（例：note/git.md）。
    发布日期取文件的创建时间（macOS 的 st_birthtime）。

详情页顶部大图：
    在对应的源配置里加 "image": "images/xxx.jpg"（相对站点根目录）即可固定；
    不写则按 slug 稳定地从 HERO_POOL 里挑一张——看起来是随机的，
    但同一篇文章重复构建永远挑同一张，不会让 git diff 反复抖动。

生成物：
    tech/<slug>/index.html      文章页
    tech/<slug>/<图片>          笔记里引用的本地图片（按原相对路径复制）
    tech/index.html             文章列表（<!-- ARTICLES:START --> 之间）
    index.html                  首页「最新文章」（同上）

=========================== 输入 -> 输出 样例 ===========================

输入（笔记 `CSS/L3.Box.md`，文件创建于 2026-02-08；最后两行取自深度学习笔记，示意公式处理）：

    ## 2.CSS box model
    box 由内到外有 padding 和 margin，`box-sizing` 决定宽高怎么算：

    ~~~css
    .box { width: 350px; padding: 25px; }
    ~~~

    <img src="\box-model.png" style="zoom:100%;" />

    $$ L = -\sum_i y_i \log p_i $$

输出（`tech/css-l3-box/index.html` 里的正文部分）：

    <article class="article">
        <h1 class="article-title">L3.Box</h1>
        <div class="post-meta">发布于 2026年2月8日 | 分类: CSS</div>
        <h2>2.CSS box model</h2>
        <p>box 由内到外有 padding 和 margin，<code>box-sizing</code> 决定宽高怎么算：</p>
        <pre><code class="language-css">.box { width: 350px; padding: 25px; }</code></pre>
        <img src="box-model.png" alt="box-model" style="zoom:100%;" loading="lazy" decoding="async">
        <div class="math-display">$$L = -\sum_i y_i \log p_i$$</div>
        <p class="article-back"><a class="read-more" href="../">← 返回技术分享</a></p>
    </article>

同时 `tech/index.html` 和 `index.html` 里各多出一张卡片：

    <div class="post-card">
        <h3 class="post-title"><a href="./css-l3-box/">L3.Box</a></h3>
        <div class="post-meta">发布于 2026年2月8日 | 分类: CSS</div>
        <p class="post-excerpt">Everything in CSS has a box around it?</p>
        <a href="./css-l3-box/" class="read-more">阅读更多</a>
    </div>

笔记里的几个毛病也会被顺手修掉：
  • Windows 风格的图片路径 `src="\image-1.png"`  ->  `src="image-1.png"`
  • 公式忘了写 aligned 导致的 “Misplaced alignment tab character &”：
        $$ a &= b \\ c &= d $$   ->   $$ \begin{aligned} a &= b \\ c &= d \end{aligned} $$
  • 顶层的 `\begin{align}` 在 `$$` 里不合法，自动换成 `aligned`

含公式的页面才会引入 KaTeX（CDN），纯文字页面不会多一次请求。
"""

from __future__ import annotations

import argparse
import html as htmllib
import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from string import Template

# ============================ 配置 ============================

NOTE_ROOT = Path("/Users/david/Library/CloudStorage/OneDrive-共享的库-onedrive/note")
SITE = Path(__file__).resolve().parent.parent
OUT = SITE / "tech"

# 笔记来源：category=None 表示「用子目录名做分类」，否则用这里指定的名称；
# prefix 用来避免不同目录的 slug 撞车（会体现在 URL 上）。
SOURCES = [
    {"root": NOTE_ROOT / "Web", "category": None, "prefix": ""},
    {"root": NOTE_ROOT / "Understanding Deep Learning", "category": "深度学习", "prefix": "dl-"},
    # pdf=True：不转内容，只生成「标题 + PDF 下载」页（页数多、公式多的讲义）
    {"root": NOTE_ROOT / "Real_Analysis", "category": "数学", "prefix": "math-", "pdf": True, "title": "Real Analysis"},
    {"root": NOTE_ROOT / "Real_Analysis2", "category": "数学", "prefix": "math-", "pdf": True, "title": "Real Analysis 2"},
    {"root": NOTE_ROOT / "Differential_Geometry", "category": "数学", "prefix": "math-", "pdf": True, "title": "Differential Geometry"},
    # 单文件也可以作为源（root 直接指向 .md）
    # 想固定详情页顶部大图：在这条配置里加 "image": "images/opt/wolf-banner.jpg"
    {"root": NOTE_ROOT / "git.md", "category": "其他", "prefix": ""},
]

# 详情页顶部大图的候选（没在源里用 "image" 指定时，按 slug 稳定地随机选一张）
HERO_POOL = [
    "images/opt/wolf-banner.jpg",
    "images/opt/tiger-banner.jpg",
]

# 含公式的页面才引入；想把 KaTeX 放到本地，把下面三个 URL 换成 ./katex/... 即可
KATEX_HEAD = """    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
            onload="renderMathInElement(document.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],macros:{'\\\\part':'\\\\partial','\\\\tr':'\\\\operatorname{tr}','\\\\grad':'\\\\nabla'}});"></script>"""

# 分组展示顺序（不在这里的分类会跟到最后）
GROUP_ORDER = ["深度学习", "数学", "HTML", "CSS", "JS", "其他"]

# 首页展示几篇
LATEST_ON_HOME = 4

# 生成区块的标记，HTML 里已预埋，不要删
START = "<!-- ARTICLES:START 由 scripts/build_tech.py 生成，请勿手改 -->"
END = "<!-- ARTICLES:END -->"

# 手写的文章（不走 Markdown 转换），但也要出现在列表里
MANUAL_ARTICLES = []

# ====================== Markdown -> HTML ======================

# 允许原样保留的行内 HTML 标签（其余尖括号会被转义）
KEEP_TAGS = re.compile(
    r"<(img|br|hr|kbd|sup|sub|mark|small|u|b|i|video|audio|source|details|summary|figure|figcaption)\b[^>]*/?>",
    re.I,
)

CODE_FENCE = re.compile(r"^(```|~~~)\s*([\w+#.-]*)\s*$")


def _esc(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _norm_path(p: str) -> str:
    """Windows 笔记里常写 src="\\image-1.png"，转成正常的相对路径"""
    if "\\" in p:
        p = p.replace("\\", "/")
        if p.startswith("/"):
            p = p.lstrip("/")
    return p


def fix_asset_paths(md: str) -> str:
    """修正 <img src> 与 ![]() 里的反斜杠路径"""
    md = re.sub(r'src="([^"]*)"', lambda m: f'src="{_norm_path(m.group(1))}"', md)
    md = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)(\))", lambda m: m.group(1) + _norm_path(m.group(2)) + m.group(3), md)
    return md


def _has_top_level_amp(tex: str) -> bool:
    """判断 & 是不是出现在任何环境之外

    bmatrix / matrix / cases 等环境内部的 & 是合法的（分隔列），
    只有环境外的 & 才会报 “Misplaced alignment tab character &”。
    """
    depth = 0
    i = 0
    while i < len(tex):
        if tex.startswith("\\begin{", i):
            depth += 1
            i += 7
            continue
        if tex.startswith("\\end{", i):
            depth -= 1
            i += 5
            continue
        if tex[i] == "\\":  # 跳过 \& 这类转义
            i += 2
            continue
        if tex[i] == "&" and depth <= 0:
            return True
        i += 1
    return False


def normalize_tex(tex: str) -> str:
    """修正笔记里常见的 LaTeX 小毛病

    1) 顶层 \begin{align} / \begin{eqnarray} 放在 $$ 里不合法，一律换成 aligned；
    2) 用了 & 对齐符号却忘了写 aligned（就是 KaTeX 报的
       “Misplaced alignment tab character &”），自动包一层 aligned。
    """
    tex = tex.strip()
    tex = re.sub(r"\\(begin|end)\{(align\*?|eqnarray\*?|flalign\*?)\}", r"\\\1{aligned}", tex)
    # 3) 上标后面跟“带参数的命令”却没加花括号（如 K^\boldsymbol T），补成 K^{\boldsymbol T}
    tex = re.sub(
        r"\^(\\(?:boldsymbol|bm|mathbf|mathrm|mathcal|mathbb|mathit|mathsf|mathtt|text|operatorname)\s+[A-Za-z0-9]+)(?![}])",
        r"^{\1}",
        tex,
    )
    if _has_top_level_amp(tex):
        tex = "\\begin{aligned}\n" + tex + "\n\\end{aligned}"
    return tex


def render_display_math(tex: str) -> str:
    return '<div class="math-display">$$' + _esc(normalize_tex(tex)) + "$$</div>"


def has_math(md: str) -> bool:
    return bool(re.search(r"\$\$|(?<!\\)\$[^$\n]+?\$", md))


def add_img_attrs(body: str) -> str:
    """给内容图片补上懒加载，首屏以下的大图不用一开始就下载"""

    def repl(m: "re.Match[str]") -> str:
        tag = m.group(0)
        if "loading=" in tag:
            return tag
        return tag.rstrip(">").rstrip("/").rstrip() + ' loading="lazy" decoding="async">'

    return re.sub(r"<img[^>]*>", repl, body)


def inline(text: str) -> str:
    """处理行内语法：$公式$、`code`、**粗体**、*斜体*、[链接](url)"""
    stash: list[str] = []

    def keep(v: str) -> str:
        stash.append(v)
        return f"\x00{len(stash) - 1}\x00"

    # 0. 行内公式先整体保护，避免被后面的转义/加粗/斜体规则破坏
    text = re.sub(r"(?<!\\)\$([^$\n]+?)\$", lambda m: keep("$" + _esc(m.group(1)) + "$"), text)
    # 1. 行内代码（内部不再解析其他语法）
    text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{_esc(m.group(1))}</code>"), text)
    # 2. 允许的原始 HTML 标签
    text = KEEP_TAGS.sub(lambda m: keep(m.group(0)), text)
    # 3. 剩余的尖括号转义，避免把 <header> 这类示例当成标签
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    # 4. 粗体 / 斜体
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)\*(?![*\w])", r"<em>\1</em>", text)
    # 5. 链接与图片
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    # 6. 还原占位符
    while "\x00" in text:
        text = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


def md_to_html(md: str) -> str:
    md = fix_asset_paths(md)
    # 有些笔记把 `#` 当章节标题用；文章标题已经是 h1，所以整篇降一级避免抢格式
    shift = 1 if re.search(r"(?m)^#\s", md) else 0
    lines = md.replace("\r\n", "\n").replace("\t", "    ").split("\n")
    out: list[str] = []
    para: list[str] = []

    def flush() -> None:
        if not para:
            return
        joined = " ".join(s.strip() for s in para)
        para.clear()
        # 单独一张图片就不要包 <p> 了
        if re.fullmatch(r"\s*(<img[^>]*>\s*)+", joined):
            out.append(joined.strip())
        else:
            out.append(f"<p>{inline(joined)}</p>")

    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()

        # 代码块
        m = CODE_FENCE.match(s)
        if m:
            flush()
            fence, lang = m.group(1), m.group(2)
            buf: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                buf.append(lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            cls = f' class="language-{_esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{_esc(chr(10).join(buf))}</code></pre>")
            continue

        # 行间公式 $$ ... $$
        if s.startswith("$$"):
            flush()
            if len(s) > 4 and s.endswith("$$"):
                tex = s[2:-2]
                i += 1
            else:
                buf = [s[2:]]
                i += 1
                while i < n and not lines[i].strip().endswith("$$"):
                    buf.append(lines[i])
                    i += 1
                if i < n:
                    buf.append(lines[i].strip()[:-2])
                    i += 1
                tex = "\n".join(buf)
            out.append(render_display_math(tex))
            continue

        # 空行
        if not s:
            flush()
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            lvl = min(6, len(m.group(1)) + shift)
            out.append(f"<h{lvl}>{inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush()
            out.append("<hr>")
            i += 1
            continue

        # 无序列表
        if re.match(r"^[-*+]\s+", s):
            flush()
            items = []
            while i < n:
                mm = re.match(r"^[-*+]\s+(.*)$", lines[i].strip())
                if not mm:
                    break
                items.append(mm.group(1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue

        # 有序列表
        if re.match(r"^\d+[.)]\s+", s):
            flush()
            items = []
            while i < n:
                mm = re.match(r"^\d+[.)]\s+(.*)$", lines[i].strip())
                if not mm:
                    break
                items.append(mm.group(1))
                i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>")
            continue

        # 引用
        if s.startswith(">"):
            flush()
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].lstrip())
                i += 1
            out.append("<blockquote>" + md_to_html("\n".join(buf)) + "</blockquote>")
            continue

        para.append(raw)
        i += 1

    flush()
    return "\n".join(out)


def plain_text(md: str) -> str:
    """取第一段正文，做摘要用"""
    for raw in md.split("\n"):
        t = raw.strip()
        if not t or t.startswith(("#", "~~~", "```", "<img", "- ", "* ", "|", ">", "!", "$")):
            continue
        t = re.sub(r"\$([^$]+)\$", r"\1", t)
        t = re.sub(r"`([^`]+)`", r"\1", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
        t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
        t = re.sub(r"<[^>]+>", "", t)
        t = re.sub(r"\\[a-zA-Z]+", "", t)
        return (t[:70] + "…") if len(t) > 70 else t
    return ""


# ========================= 页面模板 =========================

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="scripts/build_tech.py">
    <title>${title} · yyc's blog</title>
    <meta name="description" content="${excerpt}">
    <link rel="icon" href="../../images/opt/icon-64.png">
    <link rel="stylesheet" href="../../assets/style.css">
${mathhead}
</head>
<body>
    <!-- 顶部导航栏 -->
    <header>
        <nav class="navbar">
            <div class="logo">yyc's blog</div>
            <ul class="nav-links">
                <li><a href="../../index.html" class="nav-link">首页</a></li>
                <li><a href="../" class="nav-link active">技术分享</a></li>
                <li><a href="../../daily/" class="nav-link">日常分享</a></li>
                <li><a href="../../about/" class="nav-link">关于我</a></li>
            </ul>
            <div class="menu-toggle">☰</div>
        </nav>
    </header>

${hero}

    <!-- 主要内容区域 -->
    <div class="container">
        <article class="article">
            <h1 class="article-title">${title}</h1>
            <div class="post-meta">发布于 ${date} | 分类: ${category}</div>
${prevnext_top}
${content}
${prevnext_bottom}
            <p class="article-back"><a class="read-more" href="../#a-${slug}">← 返回技术分享</a></p>
        </article>
    </div>

    <!-- 页脚 -->
    <footer>
        <div class="footer-container">
            <div class="footer-left">
                <div class="footer-logo">yyc's blog</div>
                <div class="footer-copy">© <span id="year"></span></div>
            </div>
            <div class="footer-links">
                <a href="mailto:yyc114@qq.com">联系我</a>
            </div>
        </div>
    </footer>

    <script>
        // 设置页脚年份
        (function(){
            const y = new Date().getFullYear();
            const el = document.getElementById('year');
            if (el) el.textContent = y;
        })();
    </script>

    <script src="../../assets/site.js"></script>

    <script>
        // 导航栏切换功能
        document.addEventListener('DOMContentLoaded', function() {
            const menuToggle = document.querySelector('.menu-toggle');
            const navLinksContainer = document.querySelector('.nav-links');

            menuToggle.addEventListener('click', function() {
                navLinksContainer.classList.toggle('active');
            });

            document.addEventListener('click', function(e) {
                if (window.innerWidth <= 768 &&
                    !e.target.closest('.nav-links') &&
                    !e.target.closest('.menu-toggle')) {
                    navLinksContainer.classList.remove('active');
                }
            });
        });
    </script>
</body>
</html>
"""


def indent_html(body: str, spaces: int = 12) -> str:
    """给生成的 HTML 补缩进；<pre> 里的内容必须原样保留，否则代码缩进会错"""
    pad = " " * spaces
    out: list[str] = []
    inside_pre = False
    for ln in body.splitlines():
        out.append(ln if inside_pre or not ln.strip() else pad + ln)
        if "<pre" in ln:
            inside_pre = True
        if "</pre>" in ln:
            inside_pre = False
    return "\n".join(out)


def card(a: dict, prefix: str, level: int = 3) -> str:
    return f"""<div class="post-card" id="a-{a['slug']}">
    <h{level} class="post-title"><a href="{prefix}{a['slug']}/">{_esc(a['title'])}</a></h{level}>
    <div class="post-meta">发布于 {a['date']} | 分类: {_esc(a['category'])}</div>
    <p class="post-excerpt">{_esc(a['excerpt'])}</p>
    <a href="{prefix}{a['slug']}/" class="read-more">阅读更多</a>
</div>"""


def prev_next_html(prev: dict | None, nxt: dict | None, pos: tuple[int, int]) -> str:
    """同分类内的上一页 / 下一页

    顺序与「技术分享」页的分组一致（同组内按标题自然排序），
    所以读者可以在一个专题里顺序读完。
    """
    if not prev and not nxt:
        return ""
    left = (
        f'<a class="pn-link pn-prev" href="../{prev["slug"]}/">'
        f'<span class="pn-dir">← 上一篇</span><span class="pn-title">{_esc(prev["title"])}</span></a>'
    ) if prev else '<span class="pn-link"></span>'
    right = (
        f'<a class="pn-link pn-next" href="../{nxt["slug"]}/">'
        f'<span class="pn-dir">下一篇 →</span><span class="pn-title">{_esc(nxt["title"])}</span></a>'
    ) if nxt else '<span class="pn-link"></span>'
    return (
        f'<nav class="prev-next">{left}<span class="pn-pos">{pos[0]} / {pos[1]}</span>{right}</nav>'
    )


def natural_key(s: str) -> list:
    """自然排序：让 L2 排在 L10 前面，C3 排在 C10 前面"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def group_rank(name: str) -> tuple[int, str]:
    return (GROUP_ORDER.index(name) if name in GROUP_ORDER else len(GROUP_ORDER), name)


def render_grouped(articles: list[dict], prefix: str) -> str:
    """技术分享页：按分类分组 + 顶部锚点导航"""
    groups: dict[str, list[dict]] = {}
    for a in articles:
        groups.setdefault(a["category"], []).append(a)
    names = sorted(groups, key=group_rank)

    nav = ['<nav class="group-nav">']
    for i, name in enumerate(names):
        nav.append(f'    <a href="#group-{i}">{_esc(name)}<span>{len(groups[name])}</span></a>')
    nav.append("</nav>")

    blocks = []
    for i, name in enumerate(names):
        items = sorted(groups[name], key=lambda a: natural_key(a["title"]))
        cards = "\n\n".join(card(a, prefix, level=4) for a in items)
        blocks.append(
            f'<div class="article-group" id="group-{i}">\n'
            f'    <h3 class="group-title">{_esc(name)}<span class="group-count">{len(items)}</span></h3>\n\n'
            f"{indent_html(cards, 4)}\n</div>"
        )
    return "\n".join(nav) + "\n\n" + "\n\n".join(blocks)


def replace_block(path: Path, body: str, dry_run: bool) -> bool:
    src = path.read_text(encoding="utf-8")
    if START not in src or END not in src:
        raise SystemExit(f"✗ {path} 里找不到生成标记，请先加上：\n  {START}\n  {END}")
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        START + "\n" + indent_html(body) + "\n            " + END,
        src,
        flags=re.S,
    )
    if new == src:
        return False
    if not dry_run:
        path.write_text(new, encoding="utf-8")
    return True


# ========================== 主流程 ==========================


def slugify(md_path: Path, root: Path) -> str:
    rel = md_path.relative_to(root)
    cats = [re.sub(r"[^\w]+", "-", p).strip("-").lower() for p in rel.parts[:-1]]
    stem = re.sub(r"[^\w\s.-]", "", rel.stem, flags=re.UNICODE)
    stem = re.sub(r"[\s_.]+", "-", stem).strip("-").lower()
    return "-".join([c for c in cats if c] + [stem])


def birth_date(p: Path) -> tuple[datetime, str]:
    st = p.stat()
    ts = getattr(st, "st_birthtime", st.st_ctime)
    dt = datetime.fromtimestamp(ts)
    return dt, f"{dt.year}年{dt.month}月{dt.day}日"


def slugify_text(text: str) -> str:
    s = re.sub(r"[^\w\s.-]", "", text, flags=re.UNICODE)
    return re.sub(r"[\s_.]+", "-", s).strip("-").lower()


def pdf_article(cfg: dict, warnings: list[str]) -> dict | None:
    """pdf 源：只生成「标题 + 下载」页，不解析内容"""
    src: Path = cfg["root"]
    if not src.is_dir():
        warnings.append(f"跳过不存在的目录：{src}")
        return None
    pdf = src / "main.pdf"
    if not pdf.exists():
        found = sorted(src.glob("*.pdf"))
        if not found:
            warnings.append(f"{src.name}: 没找到 PDF")
            return None
        pdf = found[0]

    dt, date_str = birth_date(pdf)
    title = cfg.get("title") or src.name.replace("_", " ")
    size = pdf.stat().st_size / 1024 / 1024
    body = (
        "<p>本笔记由 LaTeX 排版后导出为 PDF，公式与排版以 PDF 为准，"
        "点击下面的按钮下载阅读。</p>\n"
        f'<p class="pdf-download"><a class="download-btn" href="main.pdf">'
        f"下载 PDF（{size:.1f} MB）</a></p>"
    )
    return {
        "title": title,
        "slug": (cfg.get("prefix") or "") + slugify_text(title),
        "date": date_str,
        "sort_date": dt.strftime("%Y-%m-%d"),
        "category": cfg.get("category") or "数学",
        "excerpt": f"LaTeX 排版的数学笔记（PDF，{size:.1f} MB）",
        "kind": "pdf",
        "src": pdf,
        "body": body,
        "math": False,
        "md_text": "",
    }


def hero_html(a: dict) -> str:
    """详情页顶部大图。路径从站点根目录算（如 images/opt/wolf-banner.jpg）"""
    path = a.get("image") or random.Random(a["slug"]).choice(HERO_POOL)
    if not re.match(r"^https?:", path):
        clean = path.replace("\\", "/").lstrip("/")
        if clean.startswith("./"):
            clean = clean[2:]
        path = "../../" + clean
    return (
        '    <div class="headimage">\n'
        f'        <img src="{_esc(path)}" alt="{_esc(a["title"])}" decoding="async" fetchpriority="high">\n'
        "    </div>"
    )


def drop_duplicate_title(md: str, title: str) -> str:
    """笔记首行是 `# 标题` 且与文件名重复时，去掉这行，避免和文章标题重复"""
    first = next((ln for ln in md.split("\n") if ln.strip()), "")
    m = re.match(r"^#\s+(.*)$", first.strip())
    if m and m.group(1).strip().lower() == title.strip().lower():
        return md.replace(first, "", 1)
    return md


def build(sources: list[dict], dry_run: bool) -> int:
    articles: list[dict] = []
    warnings: list[str] = []

    # ---------- 第一遍：收集元数据（先不写文件，因为要算上一页/下一页） ----------
    for cfg in sources:
        src: Path = cfg["root"]
        before = len(articles)

        if cfg.get("pdf"):
            a = pdf_article(cfg, warnings)
            if a:
                a["image"] = cfg.get("image")
                articles.append(a)
            print(f"  {src.name}: {len(articles) - before} 篇（PDF）")
            continue

        # 源可以是一个目录，也可以直接指向单个 .md
        if src.is_file():
            md_files = [src] if src.suffix.lower() == ".md" else []
            base = src.parent
        elif src.is_dir():
            md_files = sorted(src.rglob("*.md"))
            base = src
        else:
            warnings.append(f"跳过不存在的路径：{src}")
            continue

        for md in md_files:
            if md.name.startswith("."):
                continue
            rel = md.relative_to(base)
            text = drop_duplicate_title(md.read_text(encoding="utf-8-sig"), md.stem)
            dt, date_str = birth_date(md)
            articles.append(
                {
                    "title": md.stem,
                    "slug": (cfg.get("prefix") or "") + slugify(md, base),
                    "date": date_str,
                    "sort_date": dt.strftime("%Y-%m-%d"),
                    "category": cfg.get("category") or (rel.parts[0] if len(rel.parts) > 1 else "技术分享"),
                    "excerpt": plain_text(text),
                    "image": cfg.get("image"),
                    "kind": "md",
                    "src": md,
                    "body": add_img_attrs(md_to_html(text)),
                    "math": has_math(text),
                    "md_text": text,
                }
            )
        print(f"  {src.name}: {len(articles) - before} 篇")

    articles.sort(key=lambda a: a["sort_date"], reverse=True)
    all_articles = articles + MANUAL_ARTICLES
    all_articles.sort(key=lambda a: a["sort_date"], reverse=True)

    # ---------- 按分类分组，同组内按标题自然排序，算出上一页/下一页 ----------
    groups: dict[str, list[dict]] = {}
    for a in all_articles:
        groups.setdefault(a["category"], []).append(a)
    for items in groups.values():
        items.sort(key=lambda a: natural_key(a["title"]))
        for i, a in enumerate(items):
            a["prev"] = items[i - 1] if i > 0 else None
            a["next"] = items[i + 1] if i + 1 < len(items) else None
            a["pos"] = (i + 1, len(items))

    # ---------- 第二遍：写页面 ----------
    for a in articles:
        out_dir = OUT / a["slug"]
        if not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(
                Template(PAGE).substitute(
                    title=_esc(a["title"]),
                    slug=a["slug"],
                    hero=hero_html(a),
                    date=a["date"],
                    category=_esc(a["category"]),
                    excerpt=_esc(a["excerpt"]),
                    prevnext_top=indent_html(prev_next_html(a["prev"], a["next"], a["pos"])),
                    content=indent_html(a["body"]),
                    prevnext_bottom=indent_html(prev_next_html(a["prev"], a["next"], a["pos"])),
                    mathhead=KATEX_HEAD if a["math"] else "",
                ),
                encoding="utf-8",
            )

            if a["kind"] == "pdf":
                shutil.copy2(a["src"], out_dir / "main.pdf")
                continue

            # 复制笔记里引用的本地图片（保持相对路径）
            root = a["src"].parent
            for ref in set(re.findall(r'<img[^>]+src="([^"#?]+)"', a["md_text"])) | set(
                re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", a["md_text"])
            ):
                ref = _norm_path(ref)
                if re.match(r"^(https?:|data:|/)", ref):
                    continue
                candidate = (root / ref).resolve()
                if not candidate.exists():
                    warnings.append(f"{a['src'].name}: 找不到图片 {ref}")
                    continue
                dest = out_dir / ref
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, dest)

    # 清理已删除笔记留下的旧目录（只删脚本自己生成的）
    stale = []
    if not dry_run and OUT.is_dir():
        keep = {a["slug"] for a in articles} | {a["slug"] for a in MANUAL_ARTICLES}
        for d in OUT.iterdir():
            if d.is_dir() and d.name not in keep and (d / "index.html").exists():
                if 'content="scripts/build_tech.py"' in (d / "index.html").read_text(encoding="utf-8"):
                    shutil.rmtree(d)
                    stale.append(d.name)

    # 列表：技术分享页按分类分组，首页取最新 N 篇（不分组的流水账）
    tech_body = render_grouped(all_articles, "./")
    home_body = "\n\n".join(card(a, "./tech/") for a in all_articles[:LATEST_ON_HOME])

    changed_tech = replace_block(OUT / "index.html", tech_body, dry_run)
    changed_home = replace_block(SITE / "index.html", home_body, dry_run)

    print(f"{'[dry-run] ' if dry_run else ''}笔记转换：")
    print(f"  共 {len(articles)} 篇，列表共 {len(all_articles)} 条")
    for a in articles:
        print(f"    {a['sort_date']}  {a['category']:<6} {a['title']}  ->  tech/{a['slug']}/")
    if stale:
        print(f"  清理旧目录：{', '.join(stale)}")
    print(f"  tech/index.html {'已更新' if changed_tech else '无变化'}")
    print(f"  index.html      {'已更新' if changed_home else '无变化'}")
    if warnings:
        print("  提示：")
        for w in warnings:
            print(f"    - {w}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="把 Markdown 笔记转换成技术分享文章")
    ap.add_argument("--src", type=Path, action="append", help="只处理指定目录（可多次指定）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()
    sources = (
        [{"root": p, "category": None, "prefix": ""} for p in args.src]
        if args.src
        else SOURCES
    )
    return build(sources, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
