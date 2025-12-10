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
  console.log("Escaneie o QR Code abaixo com seu WhatsApp:");
  qrcode.generate(qr, { small: true });
});

// Ready event
client.on("ready", async () => {
  console.log("WhatsApp conectado!");

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
        console.error(`Grupo "${target}" não encontrado.`);
        console.log("Grupos disponíveis:");
        const groups = chats.filter((chat) => chat.isGroup);
        groups.forEach((g) =>
          console.log(`  - ${g.name} (${g.id._serialized})`)
        );
        await client.destroy();
        process.exit(1);
      }

      chatId = group.id._serialized;
      console.log(`Enviando mensagem para o grupo: ${group.name}`);
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
      console.log(`Enviando mensagem para: ${chatId}`);
    }

    // Send message
    await client.sendMessage(chatId, message);
    console.log("Mensagem enviada com sucesso!");

    // Wait a bit before closing
    await new Promise((resolve) => setTimeout(resolve, 1000));
    await client.destroy();
    process.exit(0);
  } catch (error) {
    console.error("Erro ao enviar mensagem:", error.message);
    await client.destroy();
    process.exit(1);
  }
});

// Authentication failure
client.on("auth_failure", (msg) => {
  console.error("Falha na autenticação:", msg);
  process.exit(1);
});

// Disconnected
client.on("disconnected", (reason) => {
  console.log("WhatsApp desconectado:", reason);
  process.exit(1);
});

// Initialize client
client.initialize().catch((error) => {
  console.error("Erro ao inicializar cliente:", error.message);
  process.exit(1);
});
