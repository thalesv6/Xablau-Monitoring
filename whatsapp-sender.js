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
  console.log("Scan the QR Code below with your WhatsApp:");
  qrcode.generate(qr, { small: true });
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
  console.log("WhatsApp connected!");

  try {
    const target = config.whatsapp.target;
    const type = config.whatsapp.type;

    let chatId;

    if (type === "group") {
      // Search for group by name or use ID directly
      const chats = await client.getChats();
      const group = chats.find(
        (chat) =>
          chat.isGroup &&
          (chat.name.toLowerCase() === target.toLowerCase() ||
            chat.id._serialized === target ||
            chat.id._serialized === target + "@g.us")
      );

      if (!group) {
        console.error(`Group "${target}" not found.`);
        console.log("Available groups:");
        const groups = chats.filter((chat) => chat.isGroup);
        groups.forEach((g) =>
          console.log(`  - ${g.name} (${g.id._serialized})`)
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

    // Send message
    const sent = await client.sendMessage(chatId, message);
    messageWasSent = true;
    console.log(
      `Message sent successfully! msgId: ${sent.id._serialized} chatId: ${chatId}`
    );

    // Aguarda ACK de entrega/servidor (ack >= 1) ou timeout
    const ackReceived = await waitForAck(sent.id._serialized);
    console.log(
      ackReceived
        ? "Ack de entrega recebido (pelo menos chegou ao servidor)."
        : "Ack não recebido dentro do timeout; pode ter falhado."
    );

    // Wait a bit before closing
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await client.destroy().catch((err) => {
      console.error("Error destroying client (ignored):", err?.message || err);
    });
    process.exit(0);
  } catch (error) {
    console.error("Error sending message:", error.message);
    await client.destroy().catch(() => {});
    process.exit(1);
  }
});

// Authentication failure
client.on("auth_failure", (msg) => {
  console.error("Authentication failure:", msg);
  process.exit(1);
});

// Disconnected
client.on("disconnected", (reason) => {
  console.log("WhatsApp disconnected:", reason);
  // If já enviamos, saímos com sucesso; caso contrário, erro
  process.exit(messageWasSent ? 0 : 1);
});

// Evita que erros de fechamento do navegador quebrem após envio bem-sucedido
process.on("unhandledRejection", (err) => {
  const msg =
    (err && err.message) || (err && err.toString()) || "Unknown rejection";
  console.error("Unhandled rejection:", msg);
  process.exit(messageWasSent || messageAcked ? 0 : 1);
});

// Initialize client
client.initialize().catch((error) => {
  console.error("Error initializing client:", error.message);
  process.exit(1);
});
