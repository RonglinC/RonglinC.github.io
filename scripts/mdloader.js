document.addEventListener("DOMContentLoaded",()=>{
    const contenDiv=document.getElementById("post-content");
    const params= new URLSearchParams(window.location.search);
    const postName=params.get("post");
    fetch(`../data/posts/${postName}.md`)
    .then((res)=>res.text())
    .then((markdown)=>{
        contenDiv.innerHTML=marked.parse(markdown);
    })
    .catch((err)=>{
        contenDiv.innerHTML="<p>Could not load post.</p>";
        console.error("Error",err);
    });
});