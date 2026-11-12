/* ==========================================================================
   全站小交互：右下角「回到顶部」按钮
   --------------------------------------------------------------------------
   用法：页面底部加 <script src="<相对路径>/assets/site.js"></script>
   按钮由脚本注入，不依赖各页面的 HTML 结构。
   ========================================================================== */
(function () {
    'use strict';

    var SHOW_AFTER = 320; // 滚动多少像素后出现

    function init() {
        if (document.querySelector('.to-top')) return;

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'to-top';
        btn.setAttribute('aria-label', '回到顶部');
        btn.title = '回到顶部';
        btn.innerHTML =
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="M12 4.2 4.6 11.6l1.4 1.4 4.9-4.9V20h2.2V8.1l4.9 4.9 1.4-1.4L12 4.2Z"/>' +
            '</svg>';

        document.body.appendChild(btn);

        function setVisible(on) {
            btn.classList.toggle('is-visible', on);
        }

        btn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        // 用哨兵元素 + IntersectionObserver 判断是否该显示，
        // 比监听 scroll 事件可靠（内层滚动容器、被动滚动都不会失效）
        if ('IntersectionObserver' in window) {
            var sentinel = document.createElement('div');
            sentinel.className = 'to-top-sentinel';
            sentinel.setAttribute('aria-hidden', 'true');
            sentinel.style.top = SHOW_AFTER + 'px';
            document.body.insertBefore(sentinel, document.body.firstChild);

            // 哨兵在视口内 = 还没滚过 SHOW_AFTER，按钮隐藏
            new IntersectionObserver(function (entries) {
                setVisible(!entries[0].isIntersecting);
            }).observe(sentinel);
            return;
        }

        // 退化方案：老浏览器直接看滚动位置
        function refresh() {
            setVisible(window.scrollY > SHOW_AFTER);
        }

        window.addEventListener('scroll', refresh, { passive: true });
        document.addEventListener('scroll', refresh, { passive: true, capture: true });
        refresh();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
