// const myImage = document.getElementById("image")

// myImage.addEventListener("click", ()=> {
//     const mySrc = myImage.getAttribute("src");
//     if(mySrc === "images/test2.png"){
//         myImage.setAttribute("src", "images/test.png");
//     } else {
//         myImage.setAttribute("src", "images/test2.png");
//     }
// });



let myButton = document.querySelector("button");
let myHeading = document.querySelector("h1");

function setUserName() {
    const myName = prompt("Please enter your name.");
    if (!myName) {
        setUserName();
    }else {
        localStorage.setItem("name", myName);
        myHeading.textContent = `Welcom to my world, ${myName}`;
    }
}

if (!localStorage.getItem("name")) {
    setUserName();
} else {
    const storedName = localStorage.getItem("name");
    myHeading.textContent = `Welcom to my world, ${myName}`;
}

myButton.addEventListener("click", () => {
    setUserName();
});