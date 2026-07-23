document.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("posts-container");
    if (!container) return;

    fetch("data/posts.json")
        .then((res) => res.json())
        .then((posts) => {
            if (!posts.length) {
                container.innerHTML = '<p class="empty-hint">No posts yet.</p>';
                return;
            }

            posts.forEach((element) => {
                const article = document.createElement("article");
                article.classList.add("post");

                article.innerHTML = `
                    <h3><a href="post.html?post=${element.slug}">${element.title}</a></h3>
                    <p class="post-meta"><em>${element.date}</em></p>
                    <p>${element.summary}</p>
                `;
                container.appendChild(article);
            });
        })
        .catch((err) => {
            container.innerHTML = '<p class="empty-hint">Failed to load posts. Try again later.</p>';
            console.error("Error loading posts:", err);
        });
});
