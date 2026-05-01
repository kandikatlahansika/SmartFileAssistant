function sendMessage() {
    let input = document.getElementById("messageInput");
    let message = input.value.trim();

    if (!message) return;

    let chatBox = document.getElementById("chatBox");

    chatBox.innerHTML += `
        <div class="message user-message">${message}</div>
    `;

    input.value = "";

    // typing indicator
    let typingId = "typing-" + Date.now();
    chatBox.innerHTML += `
        <div class="message ai-message typing" id="${typingId}">
            AI is typing<span class="dots"></span>
        </div>
    `;

    chatBox.scrollTop = chatBox.scrollHeight;

    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: message })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById(typingId).remove();

        chatBox.innerHTML += `
            <div class="message ai-message">${data.reply}</div>
        `;

        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(() => {
        document.getElementById(typingId).remove();

        chatBox.innerHTML += `
            <div class="message ai-message">Something went wrong.</div>
        `;
    });
}