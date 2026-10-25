// Einstellungen von halo.spaces – liest und schreibt über die Erweiterung
// (browser.mailCards.getSettings/setSetting), Änderungen gelten sofort
"use strict";

const api = browser.mailCards;

// Texte aus der zentralen Tabelle der Erweiterung (getTranslations)
let TABLE = {};
const t = english => TABLE[english] ?? english;

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
  // eingebettet als Kategorie in Thunderbirds Einstellungen: wie die übrigen
  // Kategorien – jeder Abschnitt mit großer Überschrift über seiner Karte
  // (wie „General“, „Language & Fonts“ …), links mit festem Abstand
  const inPrefs = new URLSearchParams(location.search).get("in") == "prefs";
  document.documentElement.classList.toggle("in-prefs", inPrefs);
  for (const [title, rows] of SECTIONS(t)) {
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
      } else if (row.type == "textarea") {
        const area = el("textarea", { id, value: settings[row.key], placeholder: row.placeholder, spellcheck: false });
        let timer = null;
        area.addEventListener("input", () => {
          clearTimeout(timer);
          timer = setTimeout(() => save(area.value), 500);
        });
        section.append(el("div", { class: "row block", id: `row-${row.key}` }, text, area));
        continue;
      } else {
        control = el("input", { id, type: "checkbox", class: "switch", checked: !!settings[row.key], role: "switch" });
        control.addEventListener("change", () => save(control.checked));
      }
      section.append(el("div", { class: "row", id: `row-${row.key}` }, text, control));
    }
    main.append(el("h2", { textContent: title }), section);
  }
}

// Treffer aus der Suche der Einstellungen (#s-<key>): Option zeigen und kurz hervorheben
function showFound() {
  const row = document.getElementById(`row-${location.hash.slice(3)}`);
  if (!location.hash.startsWith("#s-") || !row) return;
  row.scrollIntoView({ block: "center" });
  row.classList.remove("found");
  row.offsetWidth; // Hervorhebung neu starten
  row.classList.add("found");
}
window.addEventListener("hashchange", showFound);

render().then(showFound);
