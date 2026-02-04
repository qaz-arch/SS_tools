import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "SSTools.DuckTutorial",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "DuckHideNode" || nodeData.name === "DuckDecodeNode") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Add Tutorial Button
                this.addWidget("button", "使用教程", null, () => {
                    window.open("http://duck.airush.top:81/jiaocheng_jump.html", "_blank");
                });
                
                return r;
            };
        }
    },
});
