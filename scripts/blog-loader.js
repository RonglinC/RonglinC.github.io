document.addEventListener("DOMContentLoaded",()=>{
    const container = document.getElementById("posts-container");
    fetch("data/posts.json")
    .then((res)=>res.json())
    .then((posts)=>{
        posts.forEach((element) => {
            const div = document.createElement("div");
            div.classList.add("post");

            div.innerHTML=`
            <h3><a href="post.html?post=${element.slug}">${element.title}</a></h3>
            <p><em>${element.date}</em></p>
            <p>${element.summary}</p>
            `;
            container.appendChild(div);
        });
    })
    .catch((err)=>{
        container.innerHTML="<p>Failed to load posts. Try again later.</p>";
        console.error("Error loading posts:",err);
    });
});