$(function () {
    var wsScheme = window.location.protocol == "https:" ? "wss" : "ws";
    const querySocket = new WebSocket(
        wsScheme + '://'
        + window.location.host
        + '/ws/query-studies'
    );

    querySocket.onmessage = function (e) {
        // const data = JSON.parse(e.data);
        console.log(e);
        //document.querySelector('#chat-log').value += (data.message + '\n');
    };

    querySocket.onclose = function (e) {
        console.log(e);
        console.error('Chat socket closed unexpectedly');
    };

    $(".query_field").keyup(function (event) {
        if (event.keyCode === 13) {
            querySocket.send(JSON.stringify({
                query: "foooom"
            }))
        }
    });
});


// document.querySelector('#chat-message-input').focus();
// document.querySelector('#chat-message-input').onkeyup = function (e) {
//     if (e.keyCode === 13) {  // enter, return
//         document.querySelector('#chat-message-submit').click();
//     }
// };

// document.querySelector('#chat-message-submit').onclick = function (e) {
//     const messageInputDom = document.querySelector('#chat-message-input');
//     const message = messageInputDom.value;
//     chatSocket.send(JSON.stringify({
//         'message': message
//     }));
//     messageInputDom.value = '';
// };