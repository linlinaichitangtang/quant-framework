/**
 * OpenClaw 信号执行机器人 — FMZ 端策略
 *
 * 部署说明：
 * 1. 在 FMZ 平台创建新策略，粘贴此代码
 * 2. 添加交易所对象（如 WexApp 模拟盘、或真实交易所）
 * 3. 设置参数：
 *    - IsMarketOrder: 是否使用市价单（推荐 true）
 *    - MaxOrderAmount: 单笔最大下单量
 *    - AutoStopLoss: 是否自动止损
 *    - StopLossPercent: 止损百分比（默认 2%）
 *
 * 此机器人通过 GetCommand() 接收 OpenClaw 发送的 JSON 命令，
 * 解析后执行对应的交易操作。
 */

var IsMarketOrder = true;       // 市价单模式
var MaxOrderAmount = 10000;     // 单笔最大金额
var AutoStopLoss = true;        // 自动止损
var StopLossPercent = 2;        // 止损百分比

// 持仓记录（用于止损跟踪）
var positionMap = {};

function main() {
    LogReset(1);
    Log("OpenClaw信号执行机器人已启动");
    Log("交易所:", exchange.GetName());
    Log("市价单模式:", IsMarketOrder);

    // 初始化账户信息
    var acc = _C(exchange.GetAccount);
    Log("初始余额:", acc.Balance, "可用:", acc.Stocks);

    while (true) {
        var cmd = GetCommand();
        if (cmd) {
            Log("收到命令:", cmd);
            processCommand(cmd);
        }

        // 自动止损检查
        if (AutoStopLoss) {
            checkStopLoss();
        }

        // 更新状态栏
        updateStatus(acc);

        Sleep(1000);
    }
}

function processCommand(cmdStr) {
    try {
        var cmd = JSON.parse(cmdStr);
        var action = cmd.action;

        if (!action) {
            Log("命令缺少 action 字段:", cmdStr, "#FF0000");
            return;
        }

        switch (action) {
            case "buy":
                executeBuy(cmd);
                break;
            case "sell":
                executeSell(cmd);
                break;
            case "long":
                executeLong(cmd);
                break;
            case "cover_long":
                executeCoverLong(cmd);
                break;
            case "cover_short":
                executeCoverShort(cmd);
                break;
            case "query_position":
                reportPosition();
                break;
            case "query_account":
                reportAccount();
                break;
            default:
                Log("未知命令:", action, "#FF0000");
        }
    } catch (e) {
        Log("命令解析失败:", e.message, cmdStr, "#FF0000");
    }
}

function executeBuy(cmd) {
    var symbol = cmd.symbol || "";
    var price = parseFloat(cmd.price) || 0;
    var amount = parseFloat(cmd.amount) || 0;
    var stopLoss = parseFloat(cmd.stop_loss) || 0;
    var takeProfit = parseFloat(cmd.take_profit) || 0;

    if (amount <= 0) {
        Log("买入数量无效:", amount, "#FF0000");
        return;
    }

    Log("执行买入:", symbol, "数量:", amount, IsMarketOrder ? "市价" : "价格:" + price);

    var tradeInfo;
    if (IsMarketOrder) {
        tradeInfo = exchange.Buy(-1, amount);
    } else {
        tradeInfo = exchange.Buy(price, amount);
    }

    if (tradeInfo) {
        Log("买入成功:", JSON.stringify(tradeInfo), "#32CD32");
        // 记录持仓用于止损
        if (stopLoss > 0) {
            positionMap[symbol] = {
                avgCost: tradeInfo.price || price,
                amount: amount,
                stopLoss: stopLoss,
                takeProfit: takeProfit,
                signalId: cmd.signal_id || ""
            };
        }
    } else {
        Log("买入失败", "#FF0000");
    }
}

function executeSell(cmd) {
    var symbol = cmd.symbol || "";
    var price = parseFloat(cmd.price) || 0;
    var amount = parseFloat(cmd.amount) || 0;

    if (amount <= 0) {
        Log("卖出数量无效:", amount, "#FF0000");
        return;
    }

    Log("执行卖出:", symbol, "数量:", amount, IsMarketOrder ? "市价" : "价格:" + price);

    var tradeInfo;
    if (IsMarketOrder) {
        tradeInfo = exchange.Sell(-1, amount);
    } else {
        tradeInfo = exchange.Sell(price, amount);
    }

    if (tradeInfo) {
        Log("卖出成功:", JSON.stringify(tradeInfo), "#32CD32");
        delete positionMap[symbol];
    } else {
        Log("卖出失败", "#FF0000");
    }
}

function executeLong(cmd) {
    exchange.SetDirection("buy");
    var ticker = _C(exchange.GetTicker);
    var price = parseFloat(cmd.price) || ticker.Sell;
    var amount = parseFloat(cmd.amount) || 0;

    Log("执行开多:", cmd.symbol, "数量:", amount, "价格:", price);
    var tradeInfo = IsMarketOrder ? exchange.Buy(-1, amount) : exchange.Buy(price, amount);
    Log("开多结果:", tradeInfo ? JSON.stringify(tradeInfo) : "失败");
}

function executeCoverLong(cmd) {
    exchange.SetDirection("closebuy");
    var ticker = _C(exchange.GetTicker);
    var price = parseFloat(cmd.price) || ticker.Buy;
    var amount = parseFloat(cmd.amount) || 0;

    Log("执行平多:", cmd.symbol, "数量:", amount, "价格:", price);
    var tradeInfo = IsMarketOrder ? exchange.Sell(-1, amount) : exchange.Sell(price, amount);
    Log("平多结果:", tradeInfo ? JSON.stringify(tradeInfo) : "失败");
}

function executeCoverShort(cmd) {
    exchange.SetDirection("closesell");
    var ticker = _C(exchange.GetTicker);
    var price = parseFloat(cmd.price) || ticker.Sell;
    var amount = parseFloat(cmd.amount) || 0;

    Log("执行平空:", cmd.symbol, "数量:", amount, "价格:", price);
    var tradeInfo = IsMarketOrder ? exchange.Buy(-1, amount) : exchange.Buy(price, amount);
    Log("平空结果:", tradeInfo ? JSON.stringify(tradeInfo) : "失败");
}

function reportPosition() {
    var acc = _C(exchange.GetAccount);
    var positions = [];
    for (var symbol in positionMap) {
        positions.push({
            symbol: symbol,
            amount: positionMap[symbol].amount,
            avg_cost: positionMap[symbol].avgCost,
            stop_loss: positionMap[symbol].stopLoss
        });
    }
    Log("持仓查询:", JSON.stringify(positions));
}

function reportAccount() {
    var acc = _C(exchange.GetAccount);
    Log("账户查询: 余额:", acc.Balance, "冻结:", acc.FrozenBalance,
        "持仓:", acc.Stocks, "冻结持仓:", acc.FrozenStocks);
}

function checkStopLoss() {
    for (var symbol in positionMap) {
        var pos = positionMap[symbol];
        var ticker = null;
        try {
            ticker = exchange.GetTicker();
        } catch (e) {
            continue;
        }

        if (!ticker) continue;

        var currentPrice = ticker.Last;
        var pnlPercent = ((currentPrice - pos.avgCost) / pos.avgCost) * 100;

        // 止损检查
        if (pos.stopLoss > 0 && currentPrice <= pos.stopLoss) {
            Log("触发止损:", symbol, "当前价:", currentPrice, "止损价:", pos.stopLoss, "#FF0000");
            exchange.Sell(-1, pos.amount);
            delete positionMap[symbol];
            continue;
        }

        // 百分比止损
        if (StopLossPercent > 0 && pnlPercent <= -StopLossPercent) {
            Log("触发百分比止损:", symbol, "亏损:", pnlPercent.toFixed(2) + "%", "#FF0000");
            exchange.Sell(-1, pos.amount);
            delete positionMap[symbol];
            continue;
        }

        // 止盈检查
        if (pos.takeProfit > 0 && currentPrice >= pos.takeProfit) {
            Log("触发止盈:", symbol, "当前价:", currentPrice, "止盈价:", pos.takeProfit, "#32CD32");
            exchange.Sell(-1, pos.amount);
            delete positionMap[symbol];
        }
    }
}

function updateStatus(acc) {
    var posCount = Object.keys(positionMap).length;
    var tbl = {
        type: "table",
        title: "OpenClaw 信号执行机器人",
        cols: ["数据", "值"],
        rows: [
            ["交易所", exchange.GetName()],
            ["余额", acc.Balance],
            ["持仓数", posCount],
            ["市价单", IsMarketOrder ? "是" : "否"],
            ["自动止损", AutoStopLoss ? "是" : "否"],
            ["止损%", StopLossPercent + "%"],
            ["运行时间", _D()]
        ]
    };
    LogStatus("`" + JSON.stringify(tbl) + "`");
}
