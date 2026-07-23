document.addEventListener("DOMContentLoaded", () => {
    const contentDiv = document.getElementById("post-content");
    const params = new URLSearchParams(window.location.search);
    const postName = params.get("post");

    if (!postName) {
        contentDiv.innerHTML =
            '<p class="empty-hint">No post selected. Go back to the <a href="blog.html">blog</a>.</p>';
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
                document.title = `${heading.textContent.trim()} — Ronglin Chen`;
            }
        })
        .catch((err) => {
            contentDiv.innerHTML =
                '<p class="empty-hint">Could not load this post. Return to the <a href="blog.html">blog</a>.</p>';
            console.error("Error", err);
        });
});
