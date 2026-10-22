// Einstellungen von halo.spaces – liest und schreibt über die Erweiterung
// (browser.mailCards.getSettings/setSetting), Änderungen gelten sofort
"use strict";

const api = browser.mailCards;

// Texte aus der zentralen Tabelle der Erweiterung (getTranslations)
let TABLE = {};
const t = english => TABLE[english] ?? english;

const SECTIONS = () => [
  [t("Mail"), [
    { key: "previewLines", type: "select", label: t("Preview lines in the message list"),
      hint: t("takes effect after a restart"), options: [0, 1, 2, 3, 4] },
    { key: "hoverActions", label: t("Actions when hovering a message"),
      hint: t("Flag, archive, delete") },
    { key: "fullConversation", label: t("Show whole conversation"),
      hint: t("received and sent messages from all folders, newest first") },
    { key: "unreadTint", label: t("Tint unread messages"),
      hint: t("light accent colour behind unread messages, besides the dot") },
    { key: "listWidth", type: "number", label: t("Message list width"),
      hint: t("pixels; double-click the divider to reset"), reset: true },
    { key: "senderLogos", label: t("Logos from sender websites"),
      hint: t("asks only the sender’s own website (favicon, BIMI) – off: no outside requests") },
    { key: "macContactPhotos", mac: true, label: t("Photos from the Contacts app"),
      hint: t("macOS asks for access once") },
    { key: "plainTextSystemFont", label: t("Messages in system font"),
      hint: t("like Apple Mail; messages with their own font keep it – off: Thunderbird’s fonts") },
    { key: "hideDuplicateContacts", label: t("Merge duplicate contacts"),
      hint: t("display only") },
  ]],
  [t("Calendar"), [
    { key: "calendarEmoji", label: t("Emojis before event titles"),
      hint: t("🎂 birthday, 🏋️ training, 🦷 dentist …") },
    { key: "emojiCustom", type: "textarea", label: t("Own keywords"),
      hint: t("one per line, “keyword = emoji”, e.g. “Book club = 📖” – take precedence"),
      placeholder: t("Book club = 📖\nChoir = 🎶") },
    { key: "birthdays", label: t("Birthdays from the address book"),
      hint: t("separate read-only calendar") },
    { key: "calendarOffline", label: t("Offline copy for online calendars"),
      hint: t("faster loading; re-creates the calendars once") },
  ]],
  [t("Appearance"), [
    { key: "bundledTheme", label: t("halo.spaces design"), hint: t("takes effect after a restart") },
    { key: "appleIcons", label: t("Own icons"), hint: t("takes effect after a restart") },
    { key: "earlyTheme", label: t("Design without flicker at start"),
      hint: t("writes a userChrome.css into your profile; from the next start") },
  ]],
  [t("Updates"), [
    { key: "autoUpdate", label: t("Install updates at start"), hint: t("checks at most every 6 hours; active after a restart") },
  ]],
  [t("Troubleshooting"), [
    { key: "debug", label: t("Detailed log"),
      hint: t("mail-cards-debug.log in the profile, includes sender addresses") },
  ]],
];

function el(tag, props = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k == "class") node.className = v;
    else if (k in node) node[k] = v;
    else node.setAttribute(k, v);
  }
  node.append(...kids);
  return node;
}

function savedBadge() {
  return el("span", { class: "saved", textContent: t("saved") });
}

function flash(badge) {
  badge.classList.add("show");
  setTimeout(() => badge.classList.remove("show"), 1200);
}

async function render() {
  const settings = await api.getSettings();
  const { lang, table } = await api.getTranslations();
  TABLE = table;
  document.documentElement.lang = lang;
  document.title = t("halo.spaces – Settings");
  const main = document.getElementById("settings");
  main.replaceChildren();
  for (const [title, rows] of SECTIONS()) {
    const section = el("section");
    for (const row of rows) {
      if (row.mac && !settings.mac) continue;
      const id = `s-${row.key}`;
      const badge = savedBadge();
      const text = el("label", { class: "text", htmlFor: id }, row.label, badge, el("span", { class: "hint", textContent: row.hint || "" }));
      const save = async value => {
        await api.setSetting(row.key, value);
        flash(badge);
      };
      let control;
      if (row.type == "select") {
        control = el("select", { id }, ...row.options.map(o => el("option", { value: String(o), textContent: String(o) })));
        control.value = String(settings[row.key]);
        control.addEventListener("change", () => save(Number(control.value)));
      } else if (row.type == "number") {
        control = el("span", {});
        const input = el("input", { id, type: "number", min: "200", max: "1200", step: "10", value: String(settings[row.key]) });
        input.addEventListener("change", () => save(Number(input.value)));
        control.append(input);
        if (row.reset) {
          const reset = el("button", { type: "button", textContent: t("Default") });
          reset.style.marginInlineStart = "6px";
          reset.addEventListener("click", async () => {
            await save(null);
            input.value = String((await api.getSettings())[row.key]);
          });
          control.append(reset);
        }
      } else if (row.type == "textarea") {
        const area = el("textarea", { id, value: settings[row.key], placeholder: row.placeholder, spellcheck: false });
        let timer = null;
        area.addEventListener("input", () => {
          clearTimeout(timer);
          timer = setTimeout(() => save(area.value), 500);
        });
        section.append(el("div", { class: "row block" }, text, area));
        continue;
      } else {
        control = el("input", { id, type: "checkbox", class: "switch", checked: !!settings[row.key], role: "switch" });
        control.addEventListener("change", () => save(control.checked));
      }
      section.append(el("div", { class: "row" }, text, control));
    }
    main.append(el("h2", { textContent: title }), section);
  }
}

render();
