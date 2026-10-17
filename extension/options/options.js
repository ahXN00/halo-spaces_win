// Einstellungen von halo.spaces – liest und schreibt über die Erweiterung
// (browser.mailCards.getSettings/setSetting), Änderungen gelten sofort
"use strict";

const api = browser.mailCards;

const SECTIONS = de => [
  [de ? "Mail" : "Mail", [
    { key: "previewLines", type: "select", label: de ? "Vorschauzeilen in der Mailliste" : "Preview lines in the message list",
      hint: de ? "gilt nach einem Neustart" : "takes effect after a restart", options: [0, 1, 2, 3, 4] },
    { key: "hoverActions", label: de ? "Aktionen beim Überfahren einer Mail" : "Actions when hovering a message",
      hint: de ? "Markieren, Archivieren, Löschen" : "Flag, archive, delete" },
    { key: "listWidth", type: "number", label: de ? "Breite der Mailliste" : "Message list width",
      hint: de ? "Pixel; Doppelklick auf die Trennlinie setzt sie zurück" : "pixels; double-click the divider to reset", reset: true },
    { key: "senderLogos", label: de ? "Logos von Absender-Websites" : "Logos from sender websites",
      hint: de ? "fragt nur die Website des Absenders (Favicon, BIMI) – aus: keine Anfragen nach außen" : "asks only the sender’s own website (favicon, BIMI) – off: no outside requests" },
    { key: "macContactPhotos", mac: true, label: de ? "Fotos aus der Kontakte-App" : "Photos from the Contacts app",
      hint: de ? "macOS fragt einmal nach dem Zugriff" : "macOS asks for access once" },
    { key: "hideDuplicateContacts", label: de ? "Doppelte Kontakte zusammenführen" : "Merge duplicate contacts",
      hint: de ? "nur in der Anzeige" : "display only" },
  ]],
  [de ? "Kalender" : "Calendar", [
    { key: "calendarEmoji", label: de ? "Emojis vor Termintiteln" : "Emojis before event titles",
      hint: de ? "🎂 Geburtstag, 🏋️ Training, 🦷 Zahnarzt …" : "🎂 birthday, 🏋️ training, 🦷 dentist …" },
    { key: "emojiCustom", type: "textarea", label: de ? "Eigene Stichwörter" : "Own keywords",
      hint: de ? "je Zeile „Stichwort = Emoji“, z. B. „Hellas Kagran = ⚽“ – haben Vorrang" : "one per line, “keyword = emoji”, e.g. “Book club = 📖” – take precedence",
      placeholder: de ? "Hellas Kagran = ⚽\nChor = 🎶" : "Book club = 📖\nChoir = 🎶" },
    { key: "birthdays", label: de ? "Geburtstage aus dem Adressbuch" : "Birthdays from the address book",
      hint: de ? "eigener, schreibgeschützter Kalender" : "separate read-only calendar" },
    { key: "calendarOffline", label: de ? "Offline-Kopie für Online-Kalender" : "Offline copy for online calendars",
      hint: de ? "schnelleres Laden; legt die Kalender einmal neu an" : "faster loading; re-creates the calendars once" },
  ]],
  [de ? "Darstellung" : "Appearance", [
    { key: "bundledTheme", label: de ? "Design von halo.spaces" : "halo.spaces design", hint: de ? "gilt nach einem Neustart" : "takes effect after a restart" },
    { key: "appleIcons", label: de ? "Eigene Symbole" : "Own icons", hint: de ? "gilt nach einem Neustart" : "takes effect after a restart" },
  ]],
  [de ? "Fehlersuche" : "Troubleshooting", [
    { key: "debug", label: de ? "Ausführliches Protokoll" : "Detailed log",
      hint: de ? "mail-cards-debug.log im Profil, auch mit Absenderadressen" : "mail-cards-debug.log in the profile, includes sender addresses" },
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

function savedBadge(de) {
  return el("span", { class: "saved", textContent: de ? "gesichert" : "saved" });
}

function flash(badge) {
  badge.classList.add("show");
  setTimeout(() => badge.classList.remove("show"), 1200);
}

async function render() {
  const settings = await api.getSettings();
  const de = settings.german;
  document.documentElement.lang = de ? "de" : "en";
  document.title = de ? "halo.spaces – Einstellungen" : "halo.spaces – Settings";
  const main = document.getElementById("settings");
  main.replaceChildren();
  for (const [title, rows] of SECTIONS(de)) {
    const section = el("section");
    for (const row of rows) {
      if (row.mac && !settings.mac) continue;
      const id = `s-${row.key}`;
      const badge = savedBadge(de);
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
          const reset = el("button", { type: "button", textContent: de ? "Standard" : "Default" });
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
