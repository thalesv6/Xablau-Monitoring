const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const fs = require("fs");
const path = require("path");

// Read configuration
const configPath = path.join(__dirname, "config.json");
let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf8"));
} catch (error) {
  console.error("Error reading config.json:", error.message);
  process.exit(1);
}

// Get message from command line argument
// Join all arguments after script name to handle messages with special characters
const message = process.argv.slice(2).join(" ");
if (!message) {
  console.error("Error: Message not provided");
  process.exit(1);
}

// Check if WhatsApp is enabled
if (!config.whatsapp.enabled) {
  console.log("WhatsApp sending disabled in config.json");
  process.exit(0);
}

// Initialize WhatsApp client
const client = new Client({
  authStrategy: new LocalAuth({
    dataPath: path.join(__dirname, ".wwebjs_auth"),
  }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  },
});

// QR Code generation
client.on("qr", (qr) => {
  console.log("🔐 QR Code gerado - WhatsApp precisa de autenticação!");
  console.log("Scan the QR Code below with your WhatsApp:");
  qrcode.generate(qr, { small: true });
  console.log("⏳ Aguardando escaneamento do QR Code...");
});

// Loading screen event (shows progress during initialization)
client.on("loading_screen", (percent, message) => {
  console.log(`📱 Carregando WhatsApp Web: ${percent}% - ${message || ""}`);
});

// Authenticating event
client.on("authenticating", () => {
  console.log("🔑 Autenticando...");
});

let messageWasSent = false;
let messageAcked = false;

async function waitForAck(messageId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), timeoutMs);

    const handler = (msg, ack) => {
      if (msg.id && msg.id._serialized === messageId) {
        messageAcked = ack >= 1;
        clearTimeout(timer);
        client.removeListener("message_ack", handler);
        resolve(true);
      }
    };

    client.on("message_ack", handler);
  });
}

// Ready event
client.on("ready", async () => {
  const initElapsed = Date.now() - initStartTime;
  console.log(`✅ WhatsApp connected! (inicialização levou ${initElapsed}ms)`);
  const readyStartTime = Date.now();

  try {
    const target = config.whatsapp.target;
    const type = config.whatsapp.type;

    console.log(`Looking for ${type}: ${target}`);
    let chatId;

    if (type === "group") {
      // Search for group by name or use ID directly
      const chats = await client.getChats();
      const group = chats.find(
        (chat) =>
          chat.isGroup &&
          (chat.name.toLowerCase() === target.toLowerCase() ||
            chat.id._serialized === target ||
            chat.id._serialized === target + "@g.us"),
      );

      if (!group) {
        console.error(`Group "${target}" not found.`);
        console.log("Available groups:");
        const groups = chats.filter((chat) => chat.isGroup);
        groups.forEach((g) =>
          console.log(`  - ${g.name} (${g.id._serialized})`),
        );
        await client.destroy().catch(() => {});
        process.exit(1);
      }

      chatId = group.id._serialized;
      console.log(`Sending message to group: ${group.name} (id: ${chatId})`);
    } else {
      // Send to individual contact
      // Format: 5511999999999@c.us (country code + number + @c.us)
      if (target.includes("@")) {
        chatId = target;
      } else {
        // Remove any non-digit characters and add @c.us
        const number = target.replace(/\D/g, "");
        chatId = number + "@c.us";
      }
      console.log(`Sending message to: ${chatId}`);
    }

    // Send message with sendSeen disabled to avoid markedUnread errors
    console.log(`Sending message (${message.length} characters)...`);
    const sendStartTime = Date.now();
    let sent;
    try {
      sent = await client.sendMessage(chatId, message, { sendSeen: false });
      const sendElapsed = Date.now() - sendStartTime;
      messageWasSent = true;
      console.log(
        `Message sent successfully! msgId: ${sent.id._serialized} chatId: ${chatId} (took ${sendElapsed}ms)`,
      );
    } catch (sendError) {
      // If sendSeen: false didn't work, try one more time with error handling
      const errorMsg = sendError.message || sendError.toString();
      const isMarkedUnreadError =
        errorMsg.includes("markedUnread") ||
        errorMsg.includes("sendSeen") ||
        errorMsg.includes("Cannot read properties of undefined");

      if (isMarkedUnreadError) {
        console.log(
          "⚠️ Warning: Error related to sendSeen detected. Retrying without sendSeen...",
        );
        try {
          // Retry without sendSeen (already disabled, but try again)
          sent = await client.sendMessage(chatId, message, { sendSeen: false });
          messageWasSent = true;
          console.log(
            `Message sent successfully on retry! msgId: ${sent.id._serialized} chatId: ${chatId}`,
          );
        } catch (retryError) {
          console.error(
            "Error sending message even on retry:",
            retryError.message,
          );
          throw retryError;
        }
      } else {
        // Real error, re-throw
        throw sendError;
      }
    }

    // Aguarda ACK de entrega/servidor (ack >= 1) ou timeout
    if (sent && sent.id && sent.id._serialized) {
      console.log("Waiting for delivery ACK...");
      const ackStartTime = Date.now();
      const ackReceived = await waitForAck(sent.id._serialized);
      const ackElapsed = Date.now() - ackStartTime;
      console.log(
        ackReceived
          ? `Ack de entrega recebido (pelo menos chegou ao servidor). (took ${ackElapsed}ms)`
          : `Ack não recebido dentro do timeout; pode ter falhado. (waited ${ackElapsed}ms)`,
      );
    }

    const totalElapsed = Date.now() - readyStartTime;
    console.log(`Total WhatsApp operation time: ${totalElapsed}ms`);

    // Wait a bit before closing
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await client.destroy().catch((err) => {
      console.error("Error destroying client (ignored):", err?.message || err);
    });
    process.exit(0);
  } catch (error) {
    // Check if error is related to sendSeen/markedUnread (non-critical)
    const errorMsg = error.message || error.toString();
    const isMarkedUnreadError =
      errorMsg.includes("markedUnread") ||
      errorMsg.includes("sendSeen") ||
      errorMsg.includes("Cannot read properties of undefined");

    // If message was sent successfully but error is about sendSeen, consider it success
    if (messageWasSent && isMarkedUnreadError) {
      console.log(
        "⚠️ Warning: Error marking message as read, but message was sent successfully.",
      );
      console.log(
        "This is a known issue with whatsapp-web.js and can be safely ignored.",
      );
      await client.destroy().catch(() => {});
      process.exit(0);
    }

    // Otherwise, it's a real error
    console.error("Error sending message:", error.message);
    await client.destroy().catch(() => {});
    process.exit(1);
  }
});

// Authentication failure
client.on("auth_failure", (msg) => {
  clearInterval(progressInterval);
  console.error("❌ Authentication failure:", msg);
  console.error("💡 Possíveis soluções:");
  console.error(
    "   1. Delete a pasta .wwebjs_auth e escaneie o QR Code novamente",
  );
  console.error(
    "   2. Verifique se o WhatsApp Web não está conectado em outro dispositivo",
  );
  console.error("   3. Verifique sua conexão com a internet");
  process.exit(1);
});

// Disconnected
client.on("disconnected", (reason) => {
  clearInterval(progressInterval);
  console.log(`⚠️ WhatsApp disconnected: ${reason}`);
  if (reason === "NAVIGATION") {
    console.log("💡 Possível causa: WhatsApp Web foi fechado ou desconectado");
  } else if (reason === "CONNECTION_CLOSED") {
    console.log(
      "💡 Possível causa: Conexão perdida com o servidor do WhatsApp",
    );
  } else if (reason === "CONNECTION_LOST") {
    console.log("💡 Possível causa: Conexão de internet perdida");
  } else if (reason === "LOGGED_OUT") {
    console.log("💡 Possível causa: Você foi desconectado do WhatsApp Web");
    console.log(
      "   Solução: Delete .wwebjs_auth e escaneie o QR Code novamente",
    );
  }
  // If já enviamos, saímos com sucesso; caso contrário, erro
  process.exit(messageWasSent ? 0 : 1);
});

// Evita que erros de fechamento do navegador quebrem após envio bem-sucedido
process.on("unhandledRejection", (err) => {
  if (typeof progressInterval !== "undefined") {
    clearInterval(progressInterval);
  }

  const msg =
    (err && err.message) || (err && err.toString()) || "Unknown rejection";

  // Ignore markedUnread/sendSeen errors if message was sent successfully
  const isMarkedUnreadError =
    msg.includes("markedUnread") ||
    msg.includes("sendSeen") ||
    msg.includes("Cannot read properties of undefined");

  if (isMarkedUnreadError && (messageWasSent || messageAcked)) {
    console.log(
      "⚠️ Warning: Unhandled rejection related to sendSeen (ignored - message was sent)",
    );
    process.exit(0);
    return;
  }

  console.error("Unhandled rejection:", msg);
  process.exit(messageWasSent || messageAcked ? 0 : 1);
});

// Check authentication directory
const authPath = path.join(__dirname, ".wwebjs_auth");
console.log("Initializing WhatsApp client...");
console.log(`📁 Auth directory: ${authPath}`);
if (fs.existsSync(authPath)) {
  const authFiles = fs.readdirSync(authPath);
  console.log(`✅ Auth directory exists with ${authFiles.length} file(s)`);
  if (authFiles.length > 0) {
    console.log(`   Files: ${authFiles.join(", ")}`);
  }
} else {
  console.log("⚠️ Auth directory does not exist - will need QR code scan");
}

const initStartTime = Date.now();
let initProgressLogged = false;

// Log progress every 10 seconds during initialization
const progressInterval = setInterval(() => {
  const elapsed = Date.now() - initStartTime;
  const seconds = Math.floor(elapsed / 1000);
  if (!initProgressLogged && seconds >= 10) {
    console.log(`⏳ Ainda inicializando... (${seconds}s decorridos)`);
    initProgressLogged = true;
  } else if (seconds >= 20 && seconds % 10 === 0) {
    console.log(`⏳ Ainda inicializando... (${seconds}s decorridos)`);
  }
}, 10000);

client.initialize().catch((error) => {
  clearInterval(progressInterval);
  const initElapsed = Date.now() - initStartTime;
  console.error(
    `❌ Error initializing client after ${initElapsed}ms:`,
    error.message,
  );
  console.error("Stack:", error.stack);
  process.exit(1);
});

// Clear progress interval when ready
client.once("ready", () => {
  clearInterval(progressInterval);
});
