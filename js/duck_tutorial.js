import { app } from "/scripts/app.js";

app.registerExtension({
    name: "SSTools.DuckTutorial",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "DuckHideNode" || nodeData.name === "DuckDecodeNode" || nodeData.name === "DuckQREncodeNode") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Add "QR Code Content Encoder" Button only for DuckQREncodeNode
                if (nodeData.name === "DuckQREncodeNode") {
                    this.addWidget("button", "用二维码编码器定制内容", null, () => {
                        window.open("https://duckp.airush.top/dashboard", "_blank");
                    });
                }

                // Add Tutorial Video Collection Button
                this.addWidget("button", "教学视频合集", null, () => {
                    window.open("http://duck.airush.top:81/jiaocheng.html", "_blank");
                });

                // Add Local Tools Download Button
                this.addWidget("button", "本地编码/解码工具下载", null, () => {
                    window.open("http://duck.airush.top:81/sstool_jump.html", "_blank");
                });

                // Add Online Decode Tool Button
                this.addWidget("button", "在线解码工具", null, () => {
                    window.open("http://duck.airush.top:81/online_jump.html", "_blank");
                });

                // Add QQ Group Copy Button
                const qqBtn = this.addWidget("button", "交流群", null, () => {
                    const groupInfo = "一群：1020585041 二群：690810507";
                    navigator.clipboard.writeText(groupInfo).then(() => {
                        qqBtn.label = "已复制到剪切板。" + groupInfo;
                        // Force redraw to update label
                        if (this.setDirtyCanvas) {
                            this.setDirtyCanvas(true, true);
                        }
                    }).catch(err => {
                        console.error('Failed to copy text: ', err);
                        qqBtn.label = "复制失败，请手动复制";
                    });
                });

                // Helper function to add read-only text display (custom widget)
                const addTextDisplay = (node, text, color = "#888") => {
                    const widget = {
                        type: "text_display",
                        name: "text_display",
                        computeSize: function(width) {
                            // Simple estimation for height
                            const padding = 30; // Increased padding
                            const availWidth = width - padding;
                            if (availWidth <= 0) return [width, 20];
                            
                            // Estimate line count
                            let lineCount = 1;
                            let currentLen = 0;
                            for (let i = 0; i < text.length; i++) {
                                // Approx width: Chinese ~11px, others ~7px
                                currentLen += (text.charCodeAt(i) > 255) ? 12 : 7; // Slightly increased estimate
                                if (currentLen > availWidth) {
                                    lineCount++;
                                    currentLen = 0;
                                }
                            }
                            return [width, lineCount * 16 + 10];
                        },
                        draw: function(ctx, node, widget_width, y, widget_height) {
                            ctx.fillStyle = color;
                            ctx.font = "11px Arial";
                            const lineHeight = 16;
                            const maxWidth = widget_width - 30; // Increased margin
                            
                            const chars = text.split('');
                            let line = '';
                            let currentY = y + 14; // Start Y
                            
                            for (let i = 0; i < chars.length; i++) {
                                const testLine = line + chars[i];
                                const testWidth = ctx.measureText(testLine).width;
                                
                                if (testWidth > maxWidth && line.length > 0) {
                                    // Draw current line centered
                                    const lineWidth = ctx.measureText(line).width;
                                    ctx.fillText(line, (widget_width - lineWidth) / 2, currentY);
                                    
                                    line = chars[i];
                                    currentY += lineHeight;
                                } else {
                                    line = testLine;
                                }
                            }
                            // Draw last line
                            if (line.length > 0) {
                                const lineWidth = ctx.measureText(line).width;
                                ctx.fillText(line, (widget_width - lineWidth) / 2, currentY);
                            }
                        }
                    };
                    if (node.addCustomWidget) {
                        node.addCustomWidget(widget);
                    } else {
                        node.widgets = node.widgets || [];
                        node.widgets.push(widget);
                    }
                    
                    // Force node resize to fit new widget
                    node.onResize && node.onResize(node.size);
                    node.setSize && node.setSize(node.computeSize());
                };

                // Add Disclaimer Text (Custom Widget)
                addTextDisplay(this, "免责声明: 此节点为开源项目，仅用于作品内容保护和学习交流，使用即承诺符合法律法规，自愿承担全部风险与责任。");
                // Remove redundant text display for QQ group since we added a button
                
                return r;
            };
        }
    },
});
