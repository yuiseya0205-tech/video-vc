from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
import json
import uuid
import webbrowser

app = FastAPI()
clients = {}

html = """
<!DOCTYPE html>
<html>
<body>
<div id="videos" style="display:flex;gap:10px"></div>
<button onclick="share()">Share Screen</button>
<div style="margin-top:10px">
<input id="msg" style="width:200px">
<button onclick="sendMsg()">Send</button>
<div id="chat" style="margin-top:10px;width:300px;height:150px;overflow:auto;border:1px solid #000"></div>
</div>
<script>
let myID = Math.random().toString(36).slice(2);
let pc = new RTCPeerConnection();
let ws = new WebSocket("ws://localhost:8000/ws");
let videos = document.getElementById("videos");
let chat = document.getElementById("chat");

let saved = JSON.parse(localStorage.getItem("chat") || "[]");
for(let t of saved){
    let d = document.createElement("div");
    d.innerText = t;
    chat.appendChild(d);
}

let myVideo = document.createElement("video");
myVideo.autoplay = true;
myVideo.playsInline = true;
myVideo.width = 200;
myVideo.height = 150;
myVideo.setAttribute("data-id", myID);
videos.appendChild(myVideo);

let peerVideoMap = {};

pc.onicecandidate = e => { 
    if(e.candidate) ws.send(JSON.stringify({type:"candidate",candidate:e.candidate,id:myID}));
};

pc.ontrack = e => {
    let peerID = e.streams[0].id;
    if(peerID === myVideo.srcObject?.id) return;
    if(peerVideoMap[peerID]) return;
    let v = document.createElement("video");
    v.autoplay = true;
    v.playsInline = true;
    v.width = 200;
    v.height = 150;
    v.srcObject = e.streams[0];
    v.setAttribute("data-id", peerID);
    peerVideoMap[peerID] = v;
    videos.appendChild(v);
};

ws.onopen = async () => {
    let s = await navigator.mediaDevices.getUserMedia({video:true,audio:true});
    s.id = myID;
    myVideo.srcObject = s;
    s.getTracks().forEach(t=>pc.addTrack(t,s));
    let offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    ws.send(JSON.stringify({type:"offer",offer:offer,id:myID}));
};

ws.onmessage = async e => {
    let m = JSON.parse(e.data);
    if(m.id === myID) return;

    if(m.type=="offer"){
        await pc.setRemoteDescription(new RTCSessionDescription(m.offer));
        let s = await navigator.mediaDevices.getUserMedia({video:true,audio:true});
        s.id = myID;
        myVideo.srcObject = s;
        s.getTracks().forEach(t=>pc.addTrack(t,s));
        let ans = await pc.createAnswer();
        await pc.setLocalDescription(ans);
        ws.send(JSON.stringify({type:"answer",answer:ans,id:myID}));
    }
    if(m.type=="answer"){
        await pc.setRemoteDescription(new RTCSessionDescription(m.answer));
    }
    if(m.type=="candidate"){
        await pc.addIceCandidate(m.candidate);
    }
    if(m.type=="chat"){
        let d = document.createElement("div");
        d.innerText = m.text;
        chat.appendChild(d);
        saved.push(m.text);
        localStorage.setItem("chat",JSON.stringify(saved));
        chat.scrollTop = chat.scrollHeight;
    }
    if(m.type=="leave"){
        let v = peerVideoMap[m.id];
        if(v){
            v.remove();
            delete peerVideoMap[m.id];
        }
    }
};

function sendMsg(){
    let t = document.getElementById("msg").value;
    ws.send(JSON.stringify({type:"chat",text:t,id:myID}));
    let d = document.createElement("div");
    d.innerText = t;
    chat.appendChild(d);
    saved.push(t);
    localStorage.setItem("chat",JSON.stringify(saved));
    chat.scrollTop = chat.scrollHeight;
    document.getElementById("msg").value = "";
}

async function share(){
    let s = await navigator.mediaDevices.getDisplayMedia({video:true});
    s.getTracks().forEach(t=>pc.addTrack(t,s));
}
</script>
</body>
</html>
"""

@app.get("/")
async def index():
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    uid = str(uuid.uuid4())
    clients[uid] = ws
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_text()
            for k,c in clients.items():
                if c != ws:
                    await c.send_text(msg)
    except:
        del clients[uid]
        for c in clients.values():
            try:
                c.send_text(json.dumps({"type":"leave","id":uid}))
            except:
                pass

webbrowser.open("http://localhost:8000")
uvicorn.run(app, host="0.0.0.0", port=8000)
