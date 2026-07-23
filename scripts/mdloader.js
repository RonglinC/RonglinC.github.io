document.addEventListener("DOMContentLoaded", () => {
    const contentDiv = document.getElementById("post-content");
    const params = new URLSearchParams(window.location.search);
    const postName = params.get("post");

    if (!postName) {
        contentDiv.innerHTML =
            '<p class="empty-hint">未指定篇目。请从 <a href="blog.html">札记列表</a> 进入。</p>';
        return;
    }

    fetch(`data/posts/${postName}.md`)
        .then((res) => {
            if (!res.ok) throw new Error("Post not found");
            return res.text();
        })
        .then((markdown) => {
            contentDiv.innerHTML = marked.parse(markdown);
            const heading = contentDiv.querySelector("h1");
            if (heading) {
                document.title = `${heading.textContent.trim()} · 陈荣霖`;
            }
        })
        .catch((err) => {
            contentDiv.innerHTML =
                '<p class="empty-hint">未能载入此篇。请返回 <a href="blog.html">札记</a>。</p>';
            console.error("Error", err);
        });
});
