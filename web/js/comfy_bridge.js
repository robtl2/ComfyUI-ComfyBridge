import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";


function onQueuePrompt({detail}) { 
    const receiver_names = detail.names;

    sender_names = app.graph._nodes
        .filter(node => node.type === "CB_ImageSender") 
        .map(node => (node.widgets[0].value));
    
    let will_queue = false;
    for (const sender_name of sender_names) {
        if (receiver_names.includes(sender_name)) {
            will_queue = true;
            break;
        }
    }

    if (will_queue) {
        console.log("ComfyBridge queuePrompt");
        app.queuePrompt();
    } 
}

//----------------------------------
// 进度条相关
let max_progress = 0;
let progress = 0;
let ex_nodes = [];
let sender_names = [];
function onExecutingCached({ detail }) {
    // 获取所有ImageSender的name参数
    sender_names = app.graph._nodes
        .filter(node => node.type === "CB_ImageSender") 
        .map(node => (node.widgets[0].value));
    
    console.log("ComfyBridge sender_names:", sender_names);

    const _nodes = app.graph._nodes
        .filter(node => node.mode === 0) //跳过bypassed之类的nodes
        .filter(node => !node.type.toLowerCase().includes("reroute"))
        .filter(node => node.outputs.some(output => output.links !== null && output.links.length > 0))
        // 只留下可能对判断要不要加入progress队列有用的参数
        .map(node => ({ id: node.id, type: node.type, inputs: node.inputs, outputs: node.outputs, widgets: node.widgets }));

    console.log("_nodes:",_nodes)
    // 跳过缓存了的nodes
    const ignore_nodes = detail.nodes
        .map(node => parseInt(node));

    ex_nodes = [];
    const nodes = [];
    for (const node of _nodes) {
        // const outputs = node.outputs.filter(output => output.links !== null && output.links.length > 0);
        if (!ignore_nodes.includes(node.id)) {   
            ex_nodes.push(node.id);
            nodes.push(node);
        }
    }

    progress = 0;
    max_progress = 0;
    for (const node of nodes) {
        max_progress += 1;
        if (node.widgets && node.widgets.length > 0) {
            for (const widget of node.widgets) {
                if (widget.name === "steps") {
                    max_progress += widget.value;
                }
            }
        }
    }

    console.log("ComfyBridge ex_nodes:", ex_nodes);
}

function dispatchProgress(node_id) {
    if (sender_names.length > 0) {  
        const body = new FormData();
        body.append('senders', JSON.stringify(sender_names));
        body.append('progress', progress);
        body.append('max', max_progress);
        api.fetchApi("/comfyBridge_progress", { method: "POST", body, });
        console.log(`ComfyBridge node:${node_id} onProgress: ${progress}/${max_progress}`);
    }
}

function onExecuting({ detail }) {
    const node_id = Number(detail);
    if (ex_nodes.includes(node_id)) {
        progress += 1;
        dispatchProgress(node_id);
    }
}

function onProgress({ detail }) {
    const node_id = parseInt(detail.node);
    if (ex_nodes.includes(node_id)) {
        progress += 1;
        dispatchProgress(node_id);
    }
}
//----------------------------------

function main_menu_settings() {
    app.ui.settings.addSetting({
        // 因为名字取得太随意了，所以这里改一下，免得哪天遇到重名的了
        id: "cÖmfyBridge.port",
        name: "comfyBridge's socket port. default: 17777 (need restart) ",
        type: "number",
        defaultValue: 17777,
    });
}

app.registerExtension({
    name: "ComfyBridge.imageSender",

    async setup() {
        // socket收到执行队列的请求，然后server通知到了这里的页面，直接在页面执行
        api.addEventListener("ComfyBridge.QueuePrompt", onQueuePrompt);
        // 进度条相关
        api.addEventListener("progress", onProgress);
        api.addEventListener("execution_cached", onExecutingCached)
        api.addEventListener("executing", onExecuting);
        
        main_menu_settings();
    },  
});


