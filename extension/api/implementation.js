/* halo.spaces – Erweiterung zum Design (Vorschau, Absenderbilder, Adressbuch, Bereiche).
 *
 * Hängt sich in die Thread-Karten jedes about:3pane-Fensters ein und ergänzt
 *  - eine zweizeilige Textvorschau (aus der Vorschau-Eigenschaft der Nachricht,
 *    bei Bedarf über folder.fetchMsgPreviewText nachgeladen),
 *  - ein rundes Absenderbild: Adressbuchfoto → BIMI-Logo → Website-Icon → Initialen.
 */

"use strict";

var { ExtensionCommon } = ChromeUtils.importESModule(
  "resource://gre/modules/ExtensionCommon.sys.mjs"
);
var { MailServices } = ChromeUtils.importESModule(
  "resource:///modules/MailServices.sys.mjs"
);
var { DNS } = ChromeUtils.importESModule("resource:///modules/DNS.sys.mjs");
var { NetUtil } = ChromeUtils.importESModule("resource://gre/modules/NetUtil.sys.mjs");
var { MsgHdrToMimeMessage } = ChromeUtils.importESModule(
  "resource:///modules/gloda/MimeMessage.sys.mjs"
);
var { ExtensionSupport } = ChromeUtils.importESModule(
  "resource:///modules/ExtensionSupport.sys.mjs"
);
var { setTimeout, clearTimeout, setInterval, clearInterval } = ChromeUtils.importESModule(
  "resource://gre/modules/Timer.sys.mjs"
);

const STYLE_ID = "mail-cards-style";
const TOOLBAR_PREF = "extensions.mailcards.toolbarApplied";
const PREVIEW_PREF = "extensions.mailcards.previewLines";
// Reihenfolge wie in der Apple-Mail-Toolbar: Abrufen, Verfassen |
// Antworten, Allen antworten, Weiterleiten | Archiv, Löschen, Spam |
// Verschieben | Markieren … Suchfeld ganz rechts.
const APPLE_TOOLBAR = [
  "spacer",
  "get-messages",
  "write-message",
  "reply",
  "reply-all",
  "forward-inline",
  "archive",
  "delete",
  "junk",
  "move-to",
  "mark-as",
  "spacer",
  "search-bar",
];
// Gleiches Layout in den übrigen Bereichen: Knöpfe links, Suchfeld rechts.
// Adressbuch: „Neuer Kontakt“ (mit Text) | Kapsel „Neues Adressbuch · Neue Liste“.
const SPACE_TOOLBARS = {
  addressbook: ["spacer", "create-contact", "create-address-book", "create-list", "spacer", "search-bar"],
  calendar: ["spacer", "new-event", "new-task", "spacer", "search-bar"],
  tasks: ["spacer", "new-task", "new-event", "spacer", "search-bar"],
  chat: ["spacer", "spacer", "search-bar"],
  settings: ["spacer", "spacer", "search-bar"],
};
const SPACE_TOOLBAR_PREF = "extensions.mailcards.spaceToolbarsApplied";
// Feedback aus dem Hilfe-Menü geht an diese Adresse
const FEEDBACK_ADDRESS = "halo.cat@icloud.com";
// „Danke sagen“ im Info-Fenster
const DONATE_URL = "https://buymeacoffee.com/diversion";
const CACHE_FILE = "mail-cards-logos.json";
const DAY = 24 * 60 * 60 * 1000;
const HIT_TTL = 30 * DAY;
const MISS_TTL = 7 * DAY;
const FETCH_TIMEOUT = 6000;

// Kontofarben – überall gleich (Mail, Adressbuch): die in den
// Kontoeinstellungen gewählte Farbe, sonst eine feste Farbe aus dem Namen.
// Adressbücher heißen wie ihr Konto (Google, iCloud) und bekommen dieselbe.
const ACCOUNT_PALETTE = ["#0A84FF", "#30B850", "#FF8A00", "#FF2D78", "#AF52DE", "#8E8E93"];
function accountColor(name) {
  try {
    const { FolderTreeProperties } = ChromeUtils.importESModule("resource:///modules/FolderTreeProperties.sys.mjs");
    for (const server of MailServices.accounts.allServers) {
      if (server.prettyName == name) {
        const color = FolderTreeProperties.getColor(server.rootFolder.URI);
        if (color) {
          return color;
        }
        break;
      }
    }
  } catch {}
  return ACCOUNT_PALETTE[[...String(name)].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) >>> 0, 7) % ACCOUNT_PALETTE.length];
}
// Farbpunkt vor Konto- und Adressbuchnamen (Ordnerliste, Adressbuchliste):
// --mc-acc an der Zeile, gezeichnet von userChrome.css
function colorAccountRows(doc) {
  const names = new Set();
  try {
    for (const server of MailServices.accounts.allServers) {
      if (server.type != "none") {
        names.add(server.prettyName); // „Lokale Ordner“ bleibt ohne Farbe
      }
    }
  } catch {}
  const paint = () => {
    for (const li of doc.querySelectorAll("#folderTree li, #books li.bookRow")) {
      const name = (li.querySelector(":scope > .container .name, .bookRow-name")?.textContent || "").trim();
      if (names.has(name)) {
        const c = accountColor(name);
        if (li.style.getPropertyValue("--mc-acc") != c) {
          li.style.setProperty("--mc-acc", c);
        }
      } else if (li.style.getPropertyValue("--mc-acc")) {
        li.style.removeProperty("--mc-acc");
      }
    }
  };
  paint();
  if (!doc.__mcAccRows) {
    doc.__mcAccRows = true;
    const target = doc.getElementById("folderTree") || doc.getElementById("books");
    if (target) {
      let pending = false;
      new doc.defaultView.MutationObserver(() => {
        if (!pending) {
          pending = true;
          doc.defaultView.setTimeout(() => { pending = false; paint(); }, 50);
        }
      }).observe(target, { childList: true, subtree: true });
    }
    const obs = { observe: () => paint() };
    Services.obs.addObserver(obs, "server-color-changed");
    doc.defaultView.addEventListener("unload", () => Services.obs.removeObserver(obs, "server-color-changed"), { once: true });
  }
}

// sehr dunkle Farben (Schwarz, Dunkelgrau) brauchen im Dunkelmodus Hilfe
function isVeryDark(color) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(color).trim());
  if (!m) {
    return false;
  }
  const n = parseInt(m[1], 16);
  return 0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255) < 70;
}

// Adressbuch: „Total contacts …“ unten erscheint erst, wenn alle Bücher
// geladen sind – bis dahin bleibt die Zeile leer. Den zuletzt gezeigten Text
// merken und sofort zeigen; Thunderbird ersetzt ihn mit dem aktuellen Wert.
const CARD_COUNT_PREF = "extensions.mailcards.cardCountText";
function cacheCardCount(doc) {
  const el = doc?.getElementById("cardCount");
  if (!el || el.__mcCached) {
    return;
  }
  el.__mcCached = true;
  if (!el.textContent.trim()) {
    el.textContent = Services.prefs.getStringPref(CARD_COUNT_PREF, "");
  }
  const remember = () => {
    const text = el.textContent.trim();
    // nur die Gesamtzahl „aller Adressbücher“ merken (so öffnet das Adressbuch)
    if (text && el.hasAttribute("data-l10n-id") && doc.getElementById("books")?.selectedIndex == 0 &&
        text != Services.prefs.getStringPref(CARD_COUNT_PREF, "")) {
      Services.prefs.setStringPref(CARD_COUNT_PREF, text);
    }
  };
  remember();
  new doc.defaultView.MutationObserver(remember).observe(el, { childList: true, characterData: true, subtree: true });
}

// Einstellungen → Appearance: „Erscheinungsbild“ Automatisch / Hell / Dunkel.
// Schaltet zwischen Thunderbirds eingebauten Themes um; das Design folgt dem
// über prefers-color-scheme (die Themes „System“, „Light“, „Dark“).
const APPEARANCE_THEMES = {
  auto: "default-theme@mozilla.org",
  light: "thunderbird-compact-light@mozilla.org",
  dark: "thunderbird-compact-dark@mozilla.org",
};
// Adressbuch: kleine Überschrift über der Liste wie „Favoriten“ in der Mail
// und „Kalender“ im Kalender
function hookBooksHeader(cw) {
  const doc = cw.document;
  const books = doc.getElementById("books");
  if (!books || doc.getElementById("mcBooksHeader")) {
    return;
  }
  const header = doc.createElement("div");
  header.id = "mcBooksHeader";
  header.textContent = Services.locale.appLocaleAsBCP47.startsWith("de") ? "Adressbücher" : "Address Books";
  books.before(header);
}

function hookAppearanceChoice(cw) {
  const doc = cw.document;
  const colorGroup = doc.getElementById("colorGroup");
  if (!colorGroup) {
    return;
  }
  const existing = doc.getElementById("mcAppearanceGroup");
  if (existing) {
    // Thunderbird blendet beim Seitenwechsel alles ohne passende Kategorie aus
    existing.setAttribute("data-category", "paneAppearance");
    existing.hidden = colorGroup.hidden;
    return;
  }
  const de = Services.locale.appLocaleAsBCP47.startsWith("de");
  const t = (a, b) => (de ? a : b);
  const X = "http://www.w3.org/1999/xhtml";
  const group = doc.createElementNS(X, "fieldset");
  group.id = "mcAppearanceGroup";
  group.setAttribute("data-category", "paneAppearance");
  group.hidden = colorGroup.hidden;
  const legend = doc.createElementNS(X, "legend");
  legend.textContent = t("Erscheinungsbild", "Appearance");
  const row = doc.createXULElement("hbox");
  row.setAttribute("align", "center");
  const label = doc.createXULElement("label");
  label.setAttribute("value", t("Hell, dunkel oder wie macOS", "Light, dark or follow macOS"));
  label.setAttribute("flex", "1");
  const list = doc.createXULElement("menulist");
  list.id = "mcAppearance";
  const popup = doc.createXULElement("menupopup");
  for (const [value, text] of [["auto", t("Automatisch (wie macOS)", "Automatic (like macOS)")], ["light", t("Hell", "Light")], ["dark", t("Dunkel", "Dark")]]) {
    const item = doc.createXULElement("menuitem");
    item.setAttribute("value", value);
    item.setAttribute("label", text);
    popup.appendChild(item);
  }
  list.appendChild(popup);
  row.append(label, list);
  group.append(legend, row);
  colorGroup.before(group);
  const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
  const sync = async () => {
    const themes = await AddonManager.getAddonsByTypes(["theme"]);
    const active = themes.find(a => a.isActive)?.id;
    const key = Object.keys(APPEARANCE_THEMES).find(k => APPEARANCE_THEMES[k] == active);
    list.value = key || "auto";
  };
  sync();
  list.addEventListener("command", async () => {
    const addon = await AddonManager.getAddonByID(APPEARANCE_THEMES[list.value]);
    await addon?.enable();
  });
}

// Schrift auf der Kontofarbe: weiß auf dunklen, dunkel auf hellen Farben
function textOnColor(color) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(color).trim());
  if (!m) {
    return "#fff";
  }
  const lin = c => (c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  const n = parseInt(m[1], 16);
  const L = 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return L > 0.45 ? "rgba(0, 0, 0, 0.85)" : "#fff";
}

// Absender dieser Domains bekommen Initialen statt eines Firmenlogos.
const FREEMAIL = new Set([
  "gmail.com", "googlemail.com", "icloud.com", "me.com", "mac.com",
  "outlook.com", "outlook.de", "outlook.at", "hotmail.com", "hotmail.de",
  "live.com", "live.at", "msn.com", "yahoo.com", "yahoo.de", "ymail.com",
  "gmx.at", "gmx.de", "gmx.net", "gmx.ch", "web.de", "aon.at", "chello.at",
  "a1.net", "kabsi.at", "t-online.de", "freenet.de", "mail.com",
  "proton.me", "protonmail.com", "pm.me", "posteo.de", "mailbox.org",
  "aol.com", "zoho.com", "fastmail.com", "hey.com",
]);

// Zweistufige Endungen, bei denen die „Firmendomain“ drei Teile hat.
const SECOND_LEVEL = new Set([
  "co.uk", "org.uk", "ac.uk", "gov.uk", "co.at", "or.at", "ac.at", "gv.at",
  "com.au", "net.au", "org.au", "co.nz", "co.jp", "ne.jp", "com.br",
  "com.tr", "co.za", "com.mx", "com.cn", "com.hk", "co.in", "co.il",
]);

const CSS = `
#threadTree tr[is="thread-card"] .card-container {
  grid-template-columns: 16px 46px minmax(0, 1fr) !important;
}
#threadTree tr[is="thread-card"] .mc-avatar {
  width: 36px;
  height: 36px;
  margin-top: 6px;
  align-self: start;
  border-radius: 50%;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  /* wie Apple Mail: Verlauf Blaugrau → Lavendel, Initialen ~54 % des Kreises */
  background: linear-gradient(180deg, #B4CAE4, #8A97C5);
  color: #fff;
  font: 600 19px -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  letter-spacing: 0;
  user-select: none;
  pointer-events: none;
}
#threadTree tr[is="thread-card"] .mc-avatar.mc-has-img {
  background: #fff;
  box-shadow: inset 0 0 0 0.5px rgba(0, 0, 0, 0.12);
}
#threadTree tr[is="thread-card"] .mc-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
#threadTree tr[is="thread-card"] .mc-avatar.mc-small img {
  width: 62%;
  height: 62%;
  object-fit: contain;
}
#threadTree tr[is="thread-card"] .mc-preview {
  font-size: 12px;
  font-weight: 400 !important;
  line-height: 16px;
  margin-top: 1px;
  padding-inline-start: 4px;
  color: color-mix(in srgb, currentColor 58%, transparent);
  white-space: normal;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  word-break: break-word;
}
/* Ordnerliste wie Apple Mail (Attribute setzt decorateFolders) */
#folderTree li[data-mc-hide] {
  display: none !important;
}
#folderTree li[data-mc-flatten],
#folderTree li[data-mc-flatten] > ul {
  display: contents !important;
}
#folderTree li[data-mc-flatten] > .container {
  display: none !important;
}
#folderTree li[data-mode="all"] li[data-server-type] > ul {
  display: flex !important;
  flex-direction: column !important;
}
#folderTree > li[data-mode="all"] > .mode-container {
  display: none !important;
}
/* „On My Mac“ (lokale Ordner) wie bei Apple vor den Konten */
#folderTree > li[data-mode="all"] > ul {
  display: flex !important;
  flex-direction: column !important;
}
#folderTree > li[data-mode="all"] > ul > li[data-server-type="none"] {
  order: -1 !important;
}
#folderTree > li[data-mode="all"] > ul > li[data-server-type="none"] > .container .twisty {
  visibility: hidden !important;
}
/* „On My Mac“ ist wie bei Apple nur eine Überschrift (nicht anklickbar) */
#folderTree > li[data-mode="all"] > ul > li[data-server-type="none"] > .container {
  pointer-events: none !important;
  background: transparent !important;
}
#folderTree > li[data-mode] {
  border: none !important;
}
#threadTree tr[is="thread-card"].dummy .mc-avatar,
#threadTree tr[is="thread-card"][data-properties~="dummy"] .mc-avatar,
#threadTree tr[is="thread-card"][data-properties~="dummy"] .mc-preview {
  visibility: hidden;
}
`;

// ---------------------------------------------------------------------------
// Protokoll (mail-cards-debug.log im Profilordner, max. ~200 KB)
// ---------------------------------------------------------------------------

const LOG_PATH = PathUtils.join(PathUtils.profileDir, "mail-cards-debug.log");
let logChain = Promise.resolve();
let logged = 0;
function log(...parts) {
  if (++logged > 2000) {
    return;
  }
  const line =
    new Date().toISOString() +
    " " +
    parts
      .map(p => (p instanceof Error ? `${p.name}: ${p.message} @ ${p.stack?.split("\n")[0]}` : typeof p == "string" ? p : JSON.stringify(p)))
      .join(" ") +
    "\n";
  logChain = logChain
    .then(async () => {
      try {
        const info = await IOUtils.stat(LOG_PATH);
        if (info.size > 200 * 1024) {
          await IOUtils.remove(LOG_PATH);
        }
      } catch {}
      await IOUtils.writeUTF8(LOG_PATH, line, { mode: "appendOrCreate" });
    })
    .catch(() => {});
}

// ---------------------------------------------------------------------------
// Hilfsfunktionen
// ---------------------------------------------------------------------------

function orgDomain(domain) {
  // Thunderbirds Liste der Domain-Endungen (co.uk, com.pl, co.kr …)
  try {
    return Services.eTLD.getBaseDomainFromHost(domain.toLowerCase().replace(/\.$/, ""));
  } catch {}
  const parts = domain.toLowerCase().replace(/\.$/, "").split(".");
  if (parts.length <= 2) {
    return parts.join(".");
  }
  const lastTwo = parts.slice(-2).join(".");
  return SECOND_LEVEL.has(lastTwo)
    ? parts.slice(-3).join(".")
    : lastTwo;
}

function initialsFor(name, email) {
  let source = (name || "").replace(/["'<>()[\]]/g, "").trim();
  if (!source || source.includes("@")) {
    source = (email || "").split("@")[0].replace(/[._\-+0-9]+/g, " ").trim();
  }
  const words = source.split(/\s+/).filter(w => /\p{L}/u.test(w));
  if (!words.length) {
    return "?";
  }
  const first = [...words[0]][0] || "";
  const second = words.length > 1 ? [...words[words.length - 1]][0] : "";
  return (first + second).toUpperCase();
}

// Vorschautext wie in Apple Mail: Fließtext ohne Zitate, Links und
// unsichtbare Füllzeichen (Newsletter verstecken damit ihren „Preheader“).
function cleanPreview(text) {
  return (text || "")
    .replace(/[\u034f\u00ad\u200b-\u200f\u2060\ufeff]/g, "")
    .split(/\r?\n/)
    .filter(line => !/^\s*>/.test(line))
    .join(" ")
    .replace(/<https?:[^>]*>/g, "")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\[(?:image|cid):[^\]]*\]/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 300);
}

function bytesToBase64(win, bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return win.btoa(binary);
}

// Netzwerkzugriffe laufen in einer eigenen Sandbox: about:3pane verbietet
// per Content-Security-Policy Verbindungen ins Internet.
let netSandbox = null;
function sandboxFetch() {
  if (!netSandbox) {
    netSandbox = Components.utils.Sandbox(
      Services.scriptSecurityManager.getSystemPrincipal(),
      { wantGlobalProperties: ["fetch"], sandboxName: "mail-cards-net" }
    );
  }
  return netSandbox.fetch;
}

// Nur öffentliche https-Adressen – Absender bestimmen die Adresse (BIMI,
// Kontaktfotos), damit darf kein Zugriff auf lokale Geräte oder Firmennetze
// ausgelöst werden
function isPublicHttps(url) {
  try {
    const u = new URL(url);
    if (u.protocol != "https:") {
      return false;
    }
    const host = u.hostname.toLowerCase();
    return !(host == "localhost" || host.endsWith(".local") || host.endsWith(".localhost") ||
      host.endsWith(".internal") || host.endsWith(".lan") || host.endsWith(".home") ||
      /^[\d.]+$/.test(host) || host.includes(":") || !host.includes("."));
  } catch {
    return false;
  }
}

async function fetchWithTimeout(win, url, opts = {}) {
  if (!isPublicHttps(url)) {
    throw new Error("blocked url");
  }
  const request = sandboxFetch()(url, {
    credentials: "omit",
    redirect: "follow",
    ...opts,
  });
  const timeout = new Promise((_, reject) =>
    setTimeout(() => reject(new Error("timeout")), FETCH_TIMEOUT)
  );
  return Promise.race([request, timeout]);
}

// Zeitkurve wie CSS cubic-bezier(x1, y1, x2, y2)
// Ordnernamen wie in Apple Mail (Ordnerliste und Titel über der Mailliste)
function appleLabels() {
  const lang = Services.locale.appLocaleAsBCP47;
  // andere Sprachen: Thunderbirds eigene, übersetzte Namen behalten
  if (!lang.startsWith("de") && !lang.startsWith("en")) {
    return { native: true };
  }
  return lang.startsWith("de")
    ? { favourites: "Favoriten", allInboxes: "Alle Eingänge", allSent: "Alle gesendeten", onMyMac: "Auf meinem Mac",
        Inbox: "Posteingang", Drafts: "Entwürfe", SentMail: "Gesendet", Junk: "Werbung", Trash: "Papierkorb", Archive: "Archiv", Templates: "Vorlagen" }
    : { favourites: "Favourites", allInboxes: "All Inboxes", allSent: "All Sent", onMyMac: "On My Mac",
        Inbox: "Inbox", Drafts: "Drafts", SentMail: "Sent", Junk: "Junk", Trash: "Bin", Archive: "Archive", Templates: "Templates" };
}
const FOLDER_ORDER = { Inbox: 1, Drafts: 2, SentMail: 3, Junk: 4, Trash: 5, Archive: 6, Templates: 7 };
function folderRole(folder) {
  return Object.keys(FOLDER_ORDER).find(k => folder?.getFlag(Ci.nsMsgFolderFlags[k]));
}

// Titel über der Mailliste wie Apple: „All Inboxes“ bzw. „Inbox – Google“
function appleFolderTitle(folder) {
  const L = appleLabels();
  const role = folderRole(folder);
  if (/^mailbox:\/\/[^/]*smart%20mailboxes\//i.test(folder.URI)) {
    if (role == "Inbox" && !L.native) return L.allInboxes;
    if (role == "SentMail" && !L.native) return L.allSent;
    return folder.prettyName;
  }
  const name = role && !L.native ? L[role] : folder.prettyName;
  const account = folder.server?.type == "none" && !L.native ? L.onMyMac : folder.server?.prettyName;
  return account ? `${name} – ${account}` : name;
}

function cubicBezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sampleX = t => ((ax * t + bx) * t + cx) * t;
  const sampleY = t => ((ay * t + by) * t + cy) * t;
  const slopeX = t => (3 * ax * t + 2 * bx) * t + cx;
  return x => {
    if (x <= 0 || x >= 1) {
      return Math.min(1, Math.max(0, x));
    }
    let t = x;
    for (let i = 0; i < 8; i++) {
      const dx = sampleX(t) - x;
      const d = slopeX(t);
      if (Math.abs(dx) < 1e-6 || Math.abs(d) < 1e-6) {
        break;
      }
      t -= dx / d;
    }
    return sampleY(Math.min(1, Math.max(0, t)));
  };
}

// ---------------------------------------------------------------------------
// Logo-Cache (pro Domain, im Profil gespeichert)
// ---------------------------------------------------------------------------

// Fotos aus der macOS-Kontakte-App. iCloud liefert Kontaktfotos nur als Link,
// der eine iCloud-Web-Anmeldung verlangt – die Kontakte-App hat sie aber lokal.
// Ein Hilfsskript (eigener Prozess, nur lesend) legt stündlich Vorschaubilder
// und eine Zuordnungsliste (E-Mail, Name) im Profilordner „mail-cards-photos“
// ab. An den Kontakten selbst ändert sich nichts.
const MAC_PHOTOS_PREF = "extensions.mailcards.macContactPhotos";
const MAC_PHOTOS_SCRIPT = `
ObjC.import('Contacts');
ObjC.import('Foundation');
function run(argv) {
  const dir = argv[0];
  const store = $.CNContactStore.alloc.init;
  const keys = $([$.CNContactIdentifierKey, $.CNContactImageDataAvailableKey, $.CNContactThumbnailImageDataKey,
    $.CNContactEmailAddressesKey, $.CNContactGivenNameKey, $.CNContactFamilyNameKey, $.CNContactOrganizationNameKey]);
  const req = $.CNContactFetchRequest.alloc.initWithKeysToFetch(keys);
  const out = [];
  store.enumerateContactsWithFetchRequestErrorUsingBlock(req, null, function (c, stop) {
    if (!c.imageDataAvailable) return;
    const data = c.thumbnailImageData;
    if (!data || Number(data.length) == 0) return;
    const file = ObjC.unwrap(c.identifier).replace(/[^A-Za-z0-9]/g, "_") + ".img";
    data.writeToFileAtomically(dir + "/" + file, true);
    const emails = [];
    for (let i = 0; i < Number(c.emailAddresses.count); i++) {
      emails.push(String(ObjC.unwrap(c.emailAddresses.objectAtIndex(i).value)).toLowerCase());
    }
    out.push({ f: file, e: emails,
      n: (String(ObjC.unwrap(c.givenName) || "") + " " + String(ObjC.unwrap(c.familyName) || "")).trim(),
      o: String(ObjC.unwrap(c.organizationName) || "") });
  });
  $(JSON.stringify(out)).writeToFileAtomicallyEncodingError(dir + "/index.json", true, $.NSUTF8StringEncoding, null);
  return String(out.length);
}`;

const MacPhotos = {
  byEmail: new Map(), // E-Mail → Dateipfad
  byName: new Map(), // Name (klein) → Dateipfad
  version: 0,
  running: false,
  listeners: new Set(),

  folder() {
    const f = Services.dirsvc.get("ProfD", Ci.nsIFile);
    f.append("mail-cards-photos");
    return f.path;
  },

  norm(name) {
    return (name || "").normalize("NFC").replace(/\s+/g, " ").trim().toLowerCase();
  },

  async load() {
    try {
      const list = await IOUtils.readJSON(PathUtils.join(this.folder(), "index.json"));
      this.byEmail.clear();
      this.byName.clear();
      for (const entry of list) {
        const path = PathUtils.join(this.folder(), entry.f);
        for (const e of entry.e || []) {
          this.byEmail.set(e, path);
        }
        for (const n of [entry.n, entry.o]) {
          if (n && !this.byName.has(this.norm(n))) {
            this.byName.set(this.norm(n), path);
          }
        }
      }
      this.version++;
      log("mac photos loaded", { photos: list.length, emails: this.byEmail.size });
    } catch {}
  },

  // Dateipfad zum Foto eines Kontakts (über E-Mail-Adressen, sonst Name)
  lookup(emails = [], name = "") {
    for (const e of emails) {
      const hit = e && this.byEmail.get(String(e).toLowerCase());
      if (hit) {
        return hit;
      }
    }
    return this.byName.get(this.norm(name)) || null;
  },

  fileURL(path) {
    return PathUtils.toFileURI(path) + "?v=" + this.version;
  },

  // Liest die macOS-Kontakte (dafür fragt macOS einmal nach Zugriff) – nur,
  // wenn eingeschaltet (extensions.mailcards.macContactPhotos = true) oder
  // schon einmal eingerichtet (Fotoverzeichnis vorhanden)
  async enabled() {
    if (Services.prefs.prefHasUserValue(MAC_PHOTOS_PREF)) {
      return Services.prefs.getBoolPref(MAC_PHOTOS_PREF);
    }
    return IOUtils.exists(PathUtils.join(this.folder(), "index.json")).catch(() => false);
  },

  async sync() {
    if (Services.appinfo.OS != "Darwin" || this.running || !(await this.enabled())) {
      return;
    }
    this.running = true;
    const t0 = Date.now();
    const dir = this.folder();
    const script = PathUtils.join(PathUtils.tempDir, "mail-cards-contact-photos.js");
    try {
      await IOUtils.makeDirectory(dir, { ignoreExisting: true });
      await IOUtils.writeUTF8(script, MAC_PHOTOS_SCRIPT);
      const { Subprocess } = ChromeUtils.importESModule("resource://gre/modules/Subprocess.sys.mjs");
      const proc = await Subprocess.call({ command: "/usr/bin/osascript", arguments: ["-l", "JavaScript", script, dir], stderr: "pipe" });
      const killer = setTimeout(() => proc.kill(), 120000);
      const [out, err] = await Promise.all([proc.stdout.readString(), proc.stderr.readString()]);
      const { exitCode } = await proc.wait();
      clearTimeout(killer);
      log("mac photos sync", { ms: Date.now() - t0, exitCode, photos: out.trim(), err: err.trim().slice(0, 160) });
      if (exitCode == 0) {
        await this.load();
        // Dateien von Kontakten, die es nicht mehr gibt, entfernen
        const keep = new Set([...this.byEmail.values(), ...this.byName.values()]);
        for (const child of await IOUtils.getChildren(dir)) {
          if (child.endsWith(".img") && !keep.has(child)) {
            await IOUtils.remove(child).catch(() => {});
          }
        }
        this.listeners.forEach(fn => fn());
      }
    } catch (e) {
      log("mac photos sync error", String(e).slice(0, 200));
    } finally {
      this.running = false;
      await IOUtils.remove(script).catch(() => {});
    }
  },
};

class LogoCache {
  constructor() {
    this.path = PathUtils.join(PathUtils.profileDir, CACHE_FILE);
    this.entries = {};
    this.loaded = this.load();
    this.saveTimer = null;
  }

  async load() {
    try {
      this.entries = await IOUtils.readJSON(this.path);
    } catch {
      this.entries = {};
    }
  }

  get(domain) {
    const e = this.entries[domain];
    if (!e) {
      return undefined;
    }
    const ttl = e.src ? HIT_TTL : MISS_TTL;
    return Date.now() - e.t < ttl ? e : undefined;
  }

  set(domain, value) {
    this.entries[domain] = { ...value, t: Date.now() };
    this.scheduleSave();
  }

  scheduleSave() {
    if (this.saveTimer) {
      return;
    }
    this.saveTimer = setTimeout(async () => {
      this.saveTimer = null;
      try {
        await IOUtils.writeJSON(this.path, this.entries, {
          tmpPath: this.path + ".tmp",
        });
      } catch (e) {
        log("cache save failed", e);
      }
    }, 2000);
  }
}

// ---------------------------------------------------------------------------
// Absenderbilder
// ---------------------------------------------------------------------------

class AvatarResolver {
  constructor(getWindow) {
    this.getWindow = getWindow;
    this.cache = new LogoCache();
    this.byEmail = new Map(); // email -> {src, small} | null
    this.pending = new Map(); // email -> Promise
    this.domainPending = new Map();
  }

  peek(email) {
    return this.byEmail.get(email);
  }

  resolve(email) {
    if (this.byEmail.has(email)) {
      return Promise.resolve(this.byEmail.get(email));
    }
    if (!this.pending.has(email)) {
      const p = this._resolve(email)
        .catch(e => {
          log("avatar error", email, e);
          return null;
        })
        .then(result => {
          this.byEmail.set(email, result);
          this.pending.delete(email);
          return result;
        });
      this.pending.set(email, p);
    }
    return this.pending.get(email);
  }

  async _resolve(email) {
    const fromAb = await this.fromAddressBook(email);
    if (fromAb) {
      log("avatar", email, "Adressbuch");
      return { src: await this.normalize(fromAb), small: false };
    }
    const domain = email.split("@")[1];
    if (!domain) {
      return null;
    }
    const org = orgDomain(domain);
    if (FREEMAIL.has(org) || FREEMAIL.has(domain)) {
      log("avatar", email, "Initialen (Freemail)");
      return null;
    }
    const logo = await this.domainLogo(domain, org);
    log("avatar", email, logo ? `Logo ${org} (${logo.source || "Speicher"})` : "Initialen (kein Logo)");
    return logo;
  }

  // Einheitliche Größe: einfarbigen bzw. durchsichtigen Rand eines Logos
  // erkennen, wegschneiden und das Motiv mit gleichem Abstand neu zentrieren.
  // Bilder ohne erkennbaren Rand (Fotos, randlose Logos) bleiben unverändert.
  async normalize(src) {
    const win = this.getWindow();
    if (!win || !src) {
      return src;
    }
    try {
      const img = new win.Image();
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = src;
      });
      const N = 128;
      const XHTML = "http://www.w3.org/1999/xhtml";
      const canvas = win.document.createElementNS(XHTML, "canvas");
      canvas.width = canvas.height = N;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      const iw = img.naturalWidth || N;
      const ih = img.naturalHeight || N;
      const scale = Math.min(N / iw, N / ih);
      const dw = iw * scale;
      const dh = ih * scale;
      const ox = (N - dw) / 2;
      const oy = (N - dh) / 2;
      ctx.drawImage(img, ox, oy, dw, dh);
      const data = ctx.getImageData(0, 0, N, N).data;
      const at = (x, y) => {
        const i = (Math.min(N - 1, Math.max(0, Math.round(y))) * N + Math.min(N - 1, Math.max(0, Math.round(x)))) * 4;
        return [data[i], data[i + 1], data[i + 2], data[i + 3]];
      };
      const corners = [
        at(ox + 1, oy + 1), at(ox + dw - 2, oy + 1),
        at(ox + 1, oy + dh - 2), at(ox + dw - 2, oy + dh - 2),
      ];
      const opaque = corners.filter(c => c[3] > 200).length >= 3;
      // Fotos erkennt man an unterschiedlichen Ecken – die bleiben unverändert
      if (opaque) {
        const spread = k => Math.max(...corners.map(c => c[k])) - Math.min(...corners.map(c => c[k]));
        if (spread(0) + spread(1) + spread(2) > 60) {
          return src;
        }
      }
      const bg = opaque
        ? [0, 1, 2].map(k => Math.round(corners.reduce((a, c) => a + c[k], 0) / 4))
        : null;
      let minX = N, minY = N, maxX = -1, maxY = -1;
      for (let y = 0; y < N; y++) {
        for (let x = 0; x < N; x++) {
          const i = (y * N + x) * 4;
          const a = data[i + 3];
          const content = opaque
            ? a > 24 && Math.abs(data[i] - bg[0]) + Math.abs(data[i + 1] - bg[1]) + Math.abs(data[i + 2] - bg[2]) > 48
            : a > 24;
          if (content) {
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }
      if (maxX < 0) {
        return src;
      }
      const bw = maxX - minX + 1;
      const bh = maxY - minY + 1;
      // Randlose, durchsichtige Logos (z. B. ein runder Spotify-Kreis) sind
      // bereits für den Kreis gestaltet. Alle anderen Logos – zu kleine wie
      // zu große – kommen auf dieselbe Größe.
      if (!opaque && bw > N * 0.9 && bh > N * 0.9) {
        return src;
      }
      // Motiv auf ca. 69 % der Kantenlänge – passt auch diagonal in den Kreis
      const side = Math.max(bw, bh) * 1.45;
      const cx = (minX + maxX + 1) / 2;
      const cy = (minY + maxY + 1) / 2;
      const out = win.document.createElementNS(XHTML, "canvas");
      out.width = out.height = N;
      const octx = out.getContext("2d");
      octx.fillStyle = opaque ? `rgb(${bg.join(",")})` : "#fff";
      octx.fillRect(0, 0, N, N);
      octx.drawImage(canvas, cx - side / 2, cy - side / 2, side, side, 0, 0, N, N);
      return out.toDataURL("image/png");
    } catch (e) {
      log("normalize error", e);
      return src;
    }
  }

  async fromAddressBook(email) {
    let card = null;
    try {
      card = MailServices.ab.cardForEmailAddress(email);
    } catch {
      return null;
    }
    const url = card?.photoURL;
    if (url?.startsWith("data:")) {
      return url;
    }
    // Foto aus der macOS-Kontakte-App (iCloud-Fotos sind nur als Link hinterlegt)
    const local = MacPhotos.lookup([email, ...(card?.emailAddresses || [])], card?.displayName);
    if (local) {
      const win = this.getWindow();
      try {
        const buf = await IOUtils.read(local);
        return `data:image/jpeg;base64,${bytesToBase64(win, buf)}`;
      } catch {}
    }
    if (!url) {
      return null;
    }
    const win = this.getWindow();
    if (!win) {
      return null;
    }
    try {
      const res = await fetchWithTimeout(win, url);
      const buf = new Uint8Array(await res.arrayBuffer());
      const type = res.headers.get("content-type") || "image/jpeg";
      return `data:${type};base64,${bytesToBase64(win, buf)}`;
    } catch {
      return null;
    }
  }

  async domainLogo(domain, org) {
    await this.cache.loaded;
    const key = org;
    const cached = this.cache.get(key);
    if (cached) {
      if (!cached.src) {
        return null;
      }
      if (cached.n !== 2) {
        // Logo aus einer älteren Version: einmalig zuschneiden und merken
        const src = await this.normalize(cached.src);
        this.cache.set(key, { src, small: false, n: 2, source: cached.source });
        return { src, small: false, source: cached.source };
      }
      return { src: cached.src, small: false, source: cached.source };
    }
    if (!this.domainPending.has(key)) {
      const p = (async () => {
        const win = this.getWindow();
        if (!win) {
          return null;
        }
        let found = null;
        for (const d of new Set([domain, org])) {
          found = await this.bimi(win, d);
          if (found) {
            break;
          }
        }
        if (!found) {
          found = await this.siteIcon(win, org);
        }
        if (found) {
          found = { src: await this.normalize(found.src), small: false, n: 2, source: found.source };
        }
        this.cache.set(key, found || { src: null });
        return found;
      })().finally(() => this.domainPending.delete(key));
      this.domainPending.set(key, p);
    }
    return this.domainPending.get(key);
  }

  async bimi(win, domain) {
    let records;
    try {
      records = await DNS.txt(`default._bimi.${domain}`);
    } catch {
      return null;
    }
    for (const rec of records || []) {
      const txt = (rec.strings || [rec.data || ""]).join("");
      if (!/v=BIMI1/i.test(txt)) {
        continue;
      }
      const m = txt.match(/(?:^|;)\s*l=([^;\s]+)/i);
      if (!m || !m[1].startsWith("https://")) {
        continue;
      }
      try {
        const res = await fetchWithTimeout(win, m[1]);
        if (!res.ok) {
          continue;
        }
        const svg = await res.text();
        if (svg.length > 256 * 1024 || !/<svg[\s>]/i.test(svg.slice(0, 4096))) {
          continue;
        }
        return {
          src: "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg),
          small: false,
          source: "BIMI",
        };
      } catch {
        // nächster Eintrag oder nächste Quelle
      }
    }
    return null;
  }

  async siteIcon(win, org) {
    const candidates = [
      `https://${org}/apple-touch-icon.png`,
      `https://www.${org}/apple-touch-icon.png`,
    ];
    // Icons aus dem <head> der Startseite (apple-touch-icon bevorzugt)
    try {
      const res = await fetchWithTimeout(win, `https://www.${org}/`, {
        headers: { Accept: "text/html" },
      });
      if (res.ok) {
        const html = (await res.text()).slice(0, 200000);
        const base = res.url;
        const links = [...html.matchAll(/<link\b[^>]*>/gi)].map(x => x[0]);
        const scored = [];
        for (const tag of links) {
          const rel = (tag.match(/\brel\s*=\s*["']?([^"'>]+)/i) || [])[1] || "";
          const href = (tag.match(/\bhref\s*=\s*["']?([^"'\s>]+)/i) || [])[1];
          if (!href || !/icon/i.test(rel)) {
            continue;
          }
          const sizes = (tag.match(/\bsizes\s*=\s*["']?(\d+)/i) || [])[1];
          let score = Number(sizes) || 32;
          if (/apple-touch-icon/i.test(rel)) {
            score += 1000;
          }
          if (/\.svg(\?|$)/i.test(href)) {
            score += 500;
          }
          try {
            scored.push({ url: new URL(href, base).href, score });
          } catch {}
        }
        scored.sort((a, b) => b.score - a.score);
        candidates.unshift(...scored.slice(0, 3).map(s => s.url));
      }
    } catch {}
    candidates.push(`https://www.${org}/favicon.ico`, `https://${org}/favicon.ico`);

    for (const url of new Set(candidates)) {
      if (!url.startsWith("https://")) {
        continue;
      }
      try {
        const res = await fetchWithTimeout(win, url);
        const type = (res.headers.get("content-type") || "").split(";")[0];
        if (!res.ok || !type.startsWith("image/")) {
          continue;
        }
        const buf = new Uint8Array(await res.arrayBuffer());
        if (buf.length < 100 || buf.length > 512 * 1024) {
          continue;
        }
        const small = !/apple-touch-icon|\.svg/i.test(url) && buf.length < 6000;
        return {
          src: `data:${type};base64,${bytesToBase64(win, buf)}`,
          small,
          source: "Website",
        };
      } catch {}
    }
    return null;
  }
}

// CSS-Variable nur setzen, wenn sich der Wert ändert – jede Änderung am
// Wurzelelement lässt Thunderbird das ganze Fenster neu durchrechnen (~10 ms)
function setVar(el, name, value) {
  if (el && el.style.getPropertyValue(name) != value) {
    el.style.setProperty(name, value);
  }
}

// Platz, den die Toolbar rechts der Mailliste braucht: alle Knöpfe in
// natürlicher Breite, das Suchfeld mit 333 px, der kleinste Abstand nach
// „Verfassen“ (12 px), der Rand rechts und 6 px Einzug an der Listenkante
// Breite der Fensterknöpfe rechts in der Toolbar-Zeile (Windows/Linux:
// Minimieren, Maximieren, Schließen; auf dem Mac 0)
function captionWidth(doc) {
  if (Services.appinfo.OS == "Darwin") {
    return 0; // auf dem Mac sitzen sie links (Ampel)
  }
  return Math.round(doc.querySelector("#unifiedToolbarContainer .titlebar-buttonbox-container")?.getBoundingClientRect().width || 0);
}

function toolbarNeed(doc) {
  const content = doc.getElementById("unifiedToolbarContent");
  if (!content) {
    return 0;
  }
  const win = doc.defaultView;
  let need = 10 + (parseFloat(win.getComputedStyle(content).paddingInlineEnd) || 0) + 12 + captionWidth(doc);
  let afterFirst = false;
  for (const li of content.children) {
    const id = li.getAttribute("item-id");
    if (id == "spacer") {
      afterFirst = true;
      continue;
    }
    if (!afterFirst || li.hidden || !li.getBoundingClientRect().width) {
      continue;
    }
    const cs = win.getComputedStyle(li);
    const margins = (parseFloat(cs.marginInlineStart) || 0) + (id == "write-message" ? 12 : parseFloat(cs.marginInlineEnd) || 0);
    need += (id == "search-bar" ? 333 : li.getBoundingClientRect().width) + margins;
  }
  return Math.ceil(need);
}

// Kanten für die Toolbar-Zeile nur dort setzen, wo sie gebraucht werden:
// an der Wurzel ließe jede Änderung alle ~5000 Elemente neu berechnen
// (25–40 ms pro Bild – die Seitenleisten-Animation ruckelt), an der
// Toolbar-Zeile sind es ~80.
function barTarget(doc) {
  return doc.getElementById("unifiedToolbarContainer") || doc.documentElement;
}
function setBarVar(doc, name, value) {
  setVar(barTarget(doc), name, value);
}

// ---------------------------------------------------------------------------
// Kalender: Offline-Unterstützung standardmäßig an
// ---------------------------------------------------------------------------

// Online-Kalender (CalDAV, abonnierte ICS) ohne lokale Kopie lädt Thunderbird
// bei jedem Start komplett vom Server – bis dahin bleibt die Ansicht leer.
// Mit Offline-Unterstützung erscheinen die Termine sofort aus der lokalen
// Kopie, Änderungen kommen im Hintergrund nach. Eingeschaltet wird nur, wo
// die Einstellung nie angefasst wurde. Nur auf Wunsch
// (extensions.mailcards.calendarOffline = true): Thunderbird legt den
// Kalender dafür neu an (neue Kennung) – das stört Kalender, die andere
// Add-ons verwalten (TbSync, Provider), und lädt alles neu herunter.
function enableCalendarOffline() {
  if (!Services.prefs.getBoolPref("extensions.mailcards.calendarOffline", false)) {
    return 0;
  }
  let changed = 0;
  try {
    const { cal } = ChromeUtils.importESModule("resource:///modules/calendar/calUtils.sys.mjs");
    for (const calendar of cal.manager.getCalendars()) {
      if (!["caldav", "ics"].includes(calendar.type) || !/^https?:/.test(calendar.uri?.spec || "")) {
        continue;
      }
      if (calendar.getProperty("cache.supported") === false || calendar.getProperty("cache.always")) {
        continue;
      }
      if (Services.prefs.prefHasUserValue(`calendar.registry.${calendar.id}.cache.enabled`)) {
        continue; // bewusst gesetzt – so lassen
      }
      calendar.setProperty("cache.enabled", true);
      changed++;
    }
  } catch (e) {
    log("calendar offline error", String(e).slice(0, 160));
  }
  if (changed) {
    log("calendar offline enabled", { changed });
  }
  return changed;
}

// ---------------------------------------------------------------------------
// Design aus der Erweiterung (theme.css)
// ---------------------------------------------------------------------------

// Das komplette Design liegt als theme.css in der Erweiterung – so kommt es
// mit jedem Update automatisch mit, ohne userChrome.css im Profil. Liegt dort
// noch eine (ältere, manuell kopierte) userChrome.css dieses Designs, gilt
// diese und theme.css bleibt aus, damit nichts doppelt greift.
const THEME_MARKER = "Thunderbird im Stil von Apple Mail";
const ThemeSheet = {
  uri: "resource://mailcards/theme.css",
  active: false,
  init() {
    this.active = false;
    if (!Services.prefs.getBoolPref("extensions.mailcards.bundledTheme", true)) {
      return;
    }
    try {
      const file = Services.dirsvc.get("ProfD", Ci.nsIFile);
      file.append("chrome");
      file.append("userChrome.css");
      if (file.exists()) {
        const stream = Cc["@mozilla.org/network/file-input-stream;1"].createInstance(Ci.nsIFileInputStream);
        stream.init(file, -1, 0, 0);
        const head = NetUtil.readInputStreamToString(stream, Math.min(stream.available(), 4096));
        stream.close();
        if (head.includes(THEME_MARKER)) {
          log("theme: userChrome.css im Profil hat Vorrang");
          return;
        }
      }
    } catch (e) {
      log("theme check error", String(e).slice(0, 120));
    }
    this.active = true;
  },
  // alle Thunderbird-eigenen Dokumente (wie userChrome.css: chrome://-Seiten)
  // sowie die Inhalts-Tabs Adressbuch, Einstellungen, Add-ons …
  wanted(doc) {
    const url = doc?.documentURI || "";
    return url.startsWith("chrome://") ||
      /^about:(addressbook|preferences|addons|accountsettings|accountsetup|message|3pane|import|profiling)/.test(url);
  },
  apply(win) {
    if (!this.active || !win || win.__mcTheme == this.uri || !this.wanted(win.document)) {
      return;
    }
    try {
      // nach einem Update: die alte Fassung in schon offenen Seiten ersetzen
      if (win.__mcTheme) {
        try {
          win.windowUtils.removeSheetUsingURIString(win.__mcTheme, win.windowUtils.USER_SHEET);
        } catch {}
      }
      win.windowUtils.loadSheetUsingURIString(this.uri, win.windowUtils.USER_SHEET);
      win.__mcTheme = this.uri;
    } catch {}
  },
  // alle Dokumente eines Fensters – auch die der Inhalts-Tabs (Einstellungen,
  // Adressbuch …): deren Browser sind eigene Bäume, nicht Teil des Fensters
  contexts(top) {
    const roots = [top?.browsingContext];
    for (const browser of top?.document?.querySelectorAll("browser") || []) {
      roots.push(browser.browsingContext);
    }
    const all = new Set();
    for (const root of roots) {
      for (const bc of root?.getAllBrowsingContextsInSubtree?.() || []) {
        all.add(bc);
      }
    }
    return all;
  },
  applyTree(top) {
    for (const bc of this.contexts(top)) {
      this.apply(bc.window); // null für Inhalte in anderen Prozessen (Mails)
    }
  },
  removeAll() {
    for (const top of Services.wm.getEnumerator(null)) {
      for (const bc of this.contexts(top)) {
        const win = bc.window;
        if (win?.__mcTheme) {
          try {
            win.windowUtils.removeSheetUsingURIString(win.__mcTheme, win.windowUtils.USER_SHEET);
          } catch {}
          delete win.__mcTheme;
        }
      }
    }
  },
};

// ---------------------------------------------------------------------------
// Einbindung in die Kartenansicht
// ---------------------------------------------------------------------------

class CardEnhancer {
  constructor(options) {
    // Zeilenzahl der Vorschau: Einstellung extensions.mailcards.previewLines
    // (Standard 1 wie in Apple Mail, 0 = keine Vorschau).
    const lines = Services.prefs.getIntPref(PREVIEW_PREF, options.previewLines ?? 1);
    this.previewLines = Math.max(0, Math.min(4, lines));
    this.windows = new Set();
    this.restorers = [];
    this.requested = new Set();
    this.pendingPreview = new Map();
    this.previewTimer = null;
    this.fullQueue = [];
    this.fullActive = 0;
    this.stats = { quick: 0, full: { ok: 0, empty: 0, nomime: 0, error: 0 } };
    this.statsLogged = false;
    this.avatars = new AvatarResolver(() => this.anyWindow());
    this.mainWindows = new Set();
  }

  start() {
    // Wie Apple Mail: Absender, Betreff, darunter die Vorschau. Thunderbirds
    // dritte Kartenzeile wäre sonst nur eine Leerzeile über der Vorschau.
    // (einmalig – wer danach wieder 3 Zeilen wählt, behält sie)
    if (this.previewLines && !Services.prefs.getBoolPref("extensions.mailcards.rowcountApplied", false)) {
      Services.prefs.setIntPref("mail.threadpane.cardsview.rowcount", 2);
      Services.prefs.setBoolPref("extensions.mailcards.rowcountApplied", true);
    }
    this.applyToolbarOnce();
    this.applySpaceToolbarsOnce();
    // Windows/Linux: einmal beim ersten Start sagen, dass halo.spaces für
    // macOS gemacht ist und dort noch erprobt wird
    const NOTE_PREF = "extensions.mailcards.platformNoteShown";
    if (Services.appinfo.OS != "Darwin" && !Services.prefs.getBoolPref(NOTE_PREF, false)) {
      setTimeout(() => {
        const w = Services.wm.getMostRecentWindow("mail:3pane");
        if (w) {
          Services.prefs.setBoolPref(NOTE_PREF, true);
          this.openHaloWindow(w, { platformNote: true });
        }
      }, 6000);
    }
    // nach dem Start, wenn der Kalender-Manager bereit ist
    setTimeout(() => enableCalendarOffline(), 8000);
    // Fotos aus der macOS-Kontakte-App: kurz nach dem Start und dann stündlich
    MacPhotos.load();
    this.registerIconVars();
    // Unser Stylesheet in alle Thunderbird-Dokumente, für die userChrome.css
    // nicht gilt (Dialoge in Seiten, Unterdialoge, Inhalts-Tabs)
    const docObserver = {
      observe: doc => {
        try {
          const url = doc.documentURI || "";
          if (ThemeSheet.active) {
            ThemeSheet.apply(doc.defaultView);
          }
          // Termin-Details: Fenster so groß, dass alles sichtbar ist
          if (url.startsWith("chrome://calendar/content/calendar-summary-dialog.xhtml") && doc.defaultView) {
            const dlg = doc.defaultView;
            dlg.addEventListener("load", () => dlg.setTimeout(() => this.fitSummaryDialog(dlg), 250), { once: true });
          }
          // Termin-/Aufgaben-Fenster: Titel und Beschriftungen ohne Doppelpunkt
          if (url.startsWith("chrome://calendar/content/calendar-event-dialog.xhtml") && doc.defaultView) {
            const dlg = doc.defaultView;
            dlg.addEventListener("load", () => dlg.setTimeout(() => this.tidyEventDialog(dlg), 300), { once: true });
          }
          // Erinnerungen: Fenster so hoch wie die Einträge (Thunderbird merkt
          // sich sonst eine feste Größe – bei einem Eintrag viel Leerraum)
          if (url.startsWith("chrome://calendar/content/calendar-alarm-dialog.xhtml") && doc.defaultView) {
            const dlg = doc.defaultView;
            dlg.addEventListener("load", () => dlg.setTimeout(() => this.fitAlarmDialog(dlg), 200), { once: true });
          }
          if (!/^(chrome:\/\/(messenger|calendar|messenger-newsblog)\/|about:(addressbook|preferences|addons|accountsettings|accountsetup|message|3pane))/.test(url)) {
            return;
          }
          const win = doc.defaultView;
          if (/^about:(3pane|message)/.test(url) && win) {
            win.addEventListener("DOMContentLoaded", () => {
              this.hookMailContext(doc);
              // Nachricht im eigenen Fenster: Knöpfe im Mailkopf zeigen
              // – ebenso, wenn die Mail-Toolbar keine Antworten-Knöpfe hat
              // (eigene Toolbar-Anordnung), sonst fehlten sie ganz
              let replyInToolbar = false;
              try {
                const { getState } = ChromeUtils.importESModule("resource:///modules/CustomizationState.mjs");
                replyInToolbar = getState().mail?.includes("reply") ?? false;
              } catch {}
              if (url.startsWith("about:message") &&
                  (!replyInToolbar || win.top?.document.documentElement.getAttribute("windowtype") == "mail:messageWindow")) {
                doc.documentElement.setAttribute("mc-standalone", "true");
              }
            }, { once: true });
          }
          if (!win || win.__mcSheet || ThemeSheet.active) {
            return; // mit theme.css ist userChrome.css nicht nötig
          }
          // Dokumente in Chrome-Docshells bekommen userChrome.css schon selbst
          if (win.docShell?.itemType == Ci.nsIDocShellTreeItem.typeChrome) {
            return;
          }
          const file = Services.dirsvc.get("ProfD", Ci.nsIFile);
          file.append("chrome");
          file.append("userChrome.css");
          if (!file.exists()) {
            return;
          }
          const uri = Services.io.newFileURI(file).spec;
          win.windowUtils.loadSheetUsingURIString(uri, win.windowUtils.USER_SHEET);
          win.__mcSheet = uri;
        } catch (e) {
          log("doc sheet error", String(e).slice(0, 160));
        }
      },
    };
    Services.obs.addObserver(docObserver, "document-element-inserted");
    this.restorers.push(() => Services.obs.removeObserver(docObserver, "document-element-inserted"));
    const onPhotos = () => this.avatars.byEmail.clear(); // neue Fotos beim nächsten Anzeigen nutzen
    MacPhotos.listeners.add(onPhotos);
    const t1 = setTimeout(() => MacPhotos.sync(), 20000);
    const t2 = setInterval(() => MacPhotos.sync(), 3600 * 1000);
    this.restorers.push(() => {
      clearTimeout(t1);
      clearInterval(t2);
      MacPhotos.listeners.delete(onPhotos);
    });
    // Thunderbird lädt die Mailansicht (about:3pane) beim Start oft erst,
    // nachdem die Erweiterung schon läuft – darum jedes Hauptfenster
    // beobachten und seine Tabs wiederholt nach neuen Mailansichten absuchen.
    ExtensionSupport.registerWindowListener("mail-cards", {
      chromeURLs: ["chrome://messenger/content/messenger.xhtml"],
      onLoadWindow: w => this.watchMainWindow(w),
    });
  }

  watchMainWindow(w) {
    if (this.mainWindows.has(w)) {
      return;
    }
    this.mainWindows.add(w);
    log("main window", { tabs: w.document.getElementById("tabmail")?.tabInfo?.length ?? null });
    // Attribut „mc-mail“ am Hauptfenster, solange ein Mail-Tab vorne ist –
    // userChrome.css färbt Toolbar- und Tab-Leiste nur dann wie Apple Mail.
    // Rechte Kante der Seitenleiste in den übrigen Bereichen (Kalender,
    // Aufgaben, Adressbuch, Chat, Einstellungen) relativ zur Toolbar-Zeile:
    // userChrome.css färbt damit die Zeile darüber im Seitenleisten-Grau.
    const SIDEBARS = {
      calendar: () => w.document.getElementById("calSidebar"),
      tasks: () => w.document.getElementById("calSidebar"),
      chat: () => w.document.getElementById("listPaneBox"),
      addressBookTab: tab => tab.browser?.contentDocument?.getElementById("booksPane"),
      // (die animierte Leiste selbst – ihr Inhalt behält beim Ein-/Ausblenden
      // seine volle Breite)
      preferencesTab: tab => {
        const doc = tab.browser?.contentDocument;
        return doc?.getElementById("pref-category-box") || doc?.getElementById("categories");
      },
      contentTab: tab => {
        const doc = tab.browser?.contentDocument;
        const url = doc?.documentURI || "";
        return url.startsWith("about:addons") ? doc.getElementById("sidebar")
          : url.startsWith("about:accountsettings") ? doc.getElementById("accountTreeBox")
          : null;
      },
    };
    const updateSideEdge = () => {
      // während die Bereiche-Leiste animiert, nichts ans Fenster schreiben –
      // jede Variable dort kostet ein komplettes Neuberechnen (25–40 ms);
      // am Ende der Animation wird einmal ausgerichtet
      if (w.__mcSpacesAnimating) {
        return;
      }
      const d = w.document;
      const tab = d.getElementById("tabmail")?.currentTabInfo;
      const el = SIDEBARS[tab?.mode?.name]?.(tab);
      const row = d.getElementById("unifiedToolbarContainer");
      if (!el || !row) {
        barTarget(d).style.removeProperty("--mc-side-right");
        return;
      }
      const inContent = el.ownerDocument != d;
      const shift = inContent ? tab.browser.getBoundingClientRect().left : 0;
      const r = el.getBoundingClientRect();
      const rowLeft = row.getBoundingClientRect().left;
      const right = r.width ? shift + r.right - rowLeft : 0;
      setBarVar(d, "--mc-side-right", `${Math.max(0, Math.round(right))}px`);
      // Wo die Knöpfe beginnen (erster Abstandhalter der Toolbar): im
      // Adressbuch über der Kontaktkarte rechts der Liste – wie in der Mail
      // über der geöffneten Nachricht –, sonst neben der Seitenleiste.
      const content = d.getElementById("unifiedToolbarContent");
      // Bezug: erster Abstandhalter (davor liegen ausgeblendete Knöpfe anderer Bereiche)
      const start = (content?.querySelector(':scope > li[item-id="spacer"]') || content)?.getBoundingClientRect().left ?? rowLeft;
      let edge = shift + (r.width ? r.right : 0) + 12;
      // erste Knöpfe in jedem Bereich an derselben Stelle wie in der Mail
      // (Kalender und Aufgaben: „+“ wie in Apple Kalender gleich rechts der
      // Seitenleiste)
      const ownEdge = tab.mode.name == "calendar" || tab.mode.name == "tasks";
      if (this.mcButtonsLeft && !ownEdge) {
        edge = this.mcButtonsLeft;
      }
      if (tab.mode.name == "addressBookTab") {
        const cards = el.ownerDocument.getElementById("cardsPane");
        // (beim Abschalten/Update wieder abmelden – sonst richtet die alte
        // Fassung bis zum Neustart weiter aus und kämpft mit der neuen)
        if (cards && cards.__mcObserver?.owner !== this) {
          const ro = new el.ownerDocument.defaultView.ResizeObserver(() => updateSideEdge());
          ro.observe(cards);
          ro.observe(el); // Adressbuchliste ein-/ausgeblendet: Kontaktliste rückt
          el.ownerDocument.getElementById("booksSplitter") && ro.observe(el.ownerDocument.getElementById("booksSplitter"));
          cards.__mcObserver = { owner: this, ro };
          this.restorers.push(() => {
            ro.disconnect();
            delete cards.__mcObserver;
          });
        }
        // Kontaktliste so breit wie die Mailliste – dann passen Kopfzeile und
        // Knöpfe genau ins selbe Raster
        const shared = el.ownerDocument.getElementById("sharedSplitter");
        // Ziehen am Teiler im Adressbuch: flüssig (währenddessen nicht
        // angleichen), nur so weit, dass Knöpfe und Suche Platz haben; die
        // neue Breite gilt danach auch für die Mailliste
        if (shared && !shared.__mcHooked && typeof shared._updateSize == "function") {
          shared.__mcHooked = true;
          const origUpdate = shared._updateSize;
          shared._updateSize = function (size) {
            const c = cards?.getBoundingClientRect();
            const b = tab.browser?.getBoundingClientRect();
            // (ohne Wert – beim Loslassen – nur die tatsächliche Größe übernehmen)
            if (typeof size == "number" && c && b) {
              const maxRight = row.getBoundingClientRect().right - toolbarNeed(d);
              size = Math.min(size, Math.max(160, maxRight - (b.left + c.left)));
            }
            return origUpdate.call(this, size);
          };
          const onResizing = () => (shared.__mcDragging = true);
          const onResized = () => {
            if (!shared.__mcDragging) {
              return;
            }
            shared.__mcDragging = false;
            const c = cards?.getBoundingClientRect();
            const b = tab.browser?.getBoundingClientRect();
            if (c?.width && b) {
              this.mcListWidth = Math.round(c.width);
              this.mcButtonsLeft = b.left + c.right + 6;
              this.mcListPending = true; // die Mail übernimmt die Breite beim nächsten Anzeigen
            }
            updateSideEdge();
          };
          shared.addEventListener("splitter-resizing", onResizing);
          shared.addEventListener("splitter-resized", onResized);
          this.restorers.push(() => {
            shared._updateSize = origUpdate;
            shared.removeEventListener("splitter-resizing", onResizing);
            shared.removeEventListener("splitter-resized", onResized);
            delete shared.__mcHooked;
          });
        }
        // rechte Kante der Kontaktliste dort, wo in der Mail die Mailliste endet –
        // auch bei ausgeblendeter Adressbuchliste (die Liste wird dann breiter)
        const cl = cards?.getBoundingClientRect();
        if (this.mcButtonsLeft && shared && "width" in shared && !shared.__mcDragging && cl &&
            !el.ownerDocument.body.classList.contains("layout-table")) {
          const want = Math.round(this.mcButtonsLeft - 6 - (shift + cl.left));
          if (want >= 160 && Math.abs((shared.width || 0) - want) >= 1) {
            shared.width = want;
          }
        }
        const cr = cards?.getBoundingClientRect();
        if (cr?.width) {
          // Knöpfe nie über der Kontaktliste
          edge = Math.max(this.mcButtonsLeft ? edge : 0, shift + cr.right + 6);
          setBarVar(d, "--mc-ab-list-right", `${Math.round(shift + cr.right - rowLeft)}px`);
        }
      }
      const toggle = d.getElementById("spacesPinnedButton")?.getBoundingClientRect();
      if (toggle?.width) {
        edge = Math.max(edge, toggle.right + 12);
      }
      setBarVar(d, "--mc-tab-offset", `${Math.max(0, Math.round(edge - start))}px`);
      // dieselbe Kante im Fenster und die Toolbar-Zeile – für Leisten, die
      // in diese Zeile verlegt werden (Chat)
      const rr = row.getBoundingClientRect();
      // nur an den Leisten, die in die Toolbar-Zeile verlegt werden
      const rowVar = (name, value) => {
        for (const id of ["chat-view-toolbox", "viewToggle"]) {
          setVar(d.getElementById(id), name, value);
        }
      };
      rowVar("--mc-caption-w", `${captionWidth(d)}px`);
      // Minikalender der Today-Pane so breit wie der in der Kalenderleiste
      const calMm = d.getElementById("calMinimonth");
      if (calMm?.offsetWidth) {
        setVar(d.getElementById("today-minimonth"), "--mc-mm-w", `${calMm.offsetWidth}px`);
      }
      rowVar("--mc-tab-left", `${Math.round(edge)}px`);
      rowVar("--mc-row-top", `${Math.round(rr.top)}px`);
      rowVar("--mc-row-h", `${Math.round(rr.height)}px`);
      const toggle2 = d.getElementById("viewToggle");
      if (toggle2?.offsetWidth) {
        setVar(toggle2, "--mc-toggle-half", `${Math.ceil(toggle2.offsetWidth / 2)}px`);
      }
    };
    this.sideEdgeUpdaters ??= new Set();
    this.sideEdgeUpdaters.add(updateSideEdge);
    const sideRO = new w.ResizeObserver(updateSideEdge);
    for (const id of ["calSidebar", "listPaneBox", "tabmail-container"]) {
      const el = w.document.getElementById(id);
      if (el) {
        sideRO.observe(el);
      }
    }
    this.restorers.push(() => sideRO.disconnect());

    // userChrome.css gilt nicht für Seiten in eigenen Browsern (Adressbuch,
    // Einstellungen, Add-ons). Dort dasselbe Stylesheet aus dem Profil als
    // User-Sheet laden, damit Farben und Regeln überall gleich sind.
    const CONTENT_PAGES = /^about:(addressbook|preferences|addons|accountsettings|accountsetup)/;
    const sheetURI = () => {
      if (ThemeSheet.active) {
        return ThemeSheet.uri;
      }
      const file = Services.dirsvc.get("ProfD", Ci.nsIFile);
      file.append("chrome");
      file.append("userChrome.css");
      return file.exists() ? Services.io.newFileURI(file).spec : null;
    };
    // Initialen wie Apple Kontakte: Vor- und Nachname → zwei Buchstaben
    // („AW“), sonst die ersten zwei Wörter des Namens, bei einem Wort einer.
    const firstLetter = word =>
      Array.from((word || "").normalize().replaceAll(/[^\p{Letter}\p{Nd}]+/gu, ""))[0] || "";
    const initialOf = (name, card) => {
      const first = firstLetter(card?.firstName);
      const last = firstLetter(card?.lastName);
      if (first && last) {
        return (first + last).toUpperCase();
      }
      const words = (name || "").normalize().split(/\s+/).map(firstLetter).filter(Boolean);
      return words.slice(0, 2).join("").toUpperCase();
    };
    // Kontaktfotos, die sich nicht laden lassen (z. B. verwaiste Foto-Datei),
    // zeigen sonst den Ersatztext „Profile picture …“. Dann wie bei Kontakten
    // ohne Foto die Initialen anzeigen.
    const fixAvatar = (el, name, card) => {
      const img = el.shadowRoot?.querySelector("img");
      const letters = el.shadowRoot?.querySelector("span");
      if (!img || !letters || !img.getAttribute("src") || el.classList.contains("is-mail-list")) {
        return;
      }
      const fallback = () => {
        if (img.hidden || !img.getAttribute("src")) {
          return;
        }
        img.hidden = true;
        letters.textContent = initialOf(typeof name == "function" ? name() : name, card);
        letters.hidden = false;
      };
      // kein Ersatztext „Profile picture …“, auch nicht während des Ladens
      img.removeAttribute("data-l10n-id");
      img.removeAttribute("data-l10n-args");
      img.alt = "";
      if (img.complete && img.naturalWidth == 0) {
        fallback();
      } else {
        img.addEventListener("error", fallback, { once: true });
      }
    };
    const hookAvatars = cw => {
      const Avatar = cw.customElements?.get("contact-avatar");
      if (!Avatar || Avatar.prototype.__mcFix) {
        return;
      }
      const orig = Avatar.prototype.setData;
      Avatar.prototype.setData = function (opts = {}) {
        const result = orig.call(this, opts);
        const c = opts.card;
        const name = c?.displayName || c?.primaryEmail || c?.name || c?.email || opts.recipient;
        const photoURL = c?.photoURL || "";
        if (c && !c.isMailList && !photoURL.startsWith("data:")) {
          const local = MacPhotos.lookup([c.primaryEmail, ...(c.emailAddresses || [])], c.displayName || opts.recipient);
          const img = this.shadowRoot?.querySelector("img");
          const span = this.shadowRoot?.querySelector("span");
          if (local && img && span) {
            img.src = MacPhotos.fileURL(local);
            img.hidden = false;
            span.hidden = true;
          }
        }
        // ohne Foto: zwei Initialen statt Thunderbirds einem Buchstaben
        const letters = this.shadowRoot?.querySelector("span");
        if (letters && !letters.hidden && !c?.isMailList) {
          const text = initialOf(opts.recipient || name, c);
          if (text) {
            letters.textContent = text;
          }
        }
        fixAvatar(this, opts.recipient || name, c);
        return result;
      };
      Avatar.prototype.__mcFix = true;
      this.restorers.push(() => {
        Avatar.prototype.setData = orig;
        delete Avatar.prototype.__mcFix;
      });
      // Detailansicht: großes Foto aus der macOS-Kontakte-App, wenn iCloud nur den Link hat
      const photo = cw.document.getElementById("viewContactPhoto");
      if (photo) {
        const fixPhoto = () => {
          const card = cw.detailsPane?.currentCard;
          const src = photo.getAttribute("src") || "";
          if (!card || src.startsWith("data:") || src.startsWith("file:")) {
            return;
          }
          const local = MacPhotos.lookup([card.primaryEmail, ...(card.emailAddresses || [])], card.displayName);
          if (local) {
            photo.src = MacPhotos.fileURL(local);
          }
        };
        const mo = new cw.MutationObserver(fixPhoto);
        mo.observe(photo, { attributes: true, attributeFilter: ["src"] });
        fixPhoto();
        this.restorers.push(() => mo.disconnect());
      }
      // schon angezeigte Fotos ebenfalls prüfen
      for (const el of cw.document.querySelectorAll("contact-avatar")) {
        fixAvatar(el, () =>
          el.closest(".card-container")?.querySelector(".name")?.textContent ||
          cw.document.getElementById("viewContactName")?.textContent || "");
      }
    };

    // Adressbuch: doppelte Kontakte zusammenführen (nur in der Anzeige – an den
    // Kontakten in Google/iCloud ändert sich nichts). Gleich ist, was denselben
    // Namen hat und dieselbe E-Mail-Adresse oder bei einem von beiden keine.
    // Von mehreren gleichen bleibt der vollständigste Eintrag stehen.
    // Ein-/ausschalten im Darstellungsmenü der Kontaktliste.
    const DEDUPE_PREF = "extensions.mailcards.hideDuplicateContacts";
    const dedupeRows = rows => {
      const score = card => {
        let n = 0;
        try {
          n = card.vCardProperties?.entries?.length || 0;
        } catch {}
        // lokal gespeicherte Fotos zeigen sicher an, Web-Adressen (iCloud) oft nicht
        const photo = card.photoURL || "";
        return n + (/^(data|file|moz-icon):/.test(photo) ? 6 : photo ? 1 : 0);
      };
      const norm = t => (t || "").normalize("NFC").replace(/\s+/g, " ").trim().toLowerCase();
      const groups = new Map(); // Name → Liste von Clustern { email, best, rows }
      const keep = new Set();
      for (const row of rows) {
        const card = row.card;
        if (!card || card.isMailList) {
          keep.add(row);
          continue;
        }
        // der Name, den die Liste anzeigt (auch Firma, wenn kein Name gesetzt ist)
        let shown = "";
        try {
          shown = row.getText?.("GeneratedName") || "";
        } catch {}
        const name = norm(shown) || norm(card.displayName) ||
          norm(`${card.firstName || ""} ${card.lastName || ""}`);
        const email = norm(card.primaryEmail);
        if (!name) {
          keep.add(row);
          continue;
        }
        const clusters = groups.get(name) || [];
        groups.set(name, clusters);
        let cluster = clusters.find(c => !email || !c.email || c.email == email);
        if (!cluster) {
          cluster = { email, best: row, rows: [row] };
          clusters.push(cluster);
          continue;
        }
        cluster.rows.push(row);
        if (!cluster.email && email) {
          cluster.email = email;
        }
        if (score(card) > score(cluster.best.card)) {
          cluster.best = row;
        }
      }
      for (const clusters of groups.values()) {
        for (const c of clusters) {
          keep.add(c.best);
          // in welchen Adressbüchern es diesen Kontakt gibt (für die Labels)
          c.best.mcSources = [...new Set(c.rows.map(r => r.directory?.dirName).filter(Boolean))];
        }
      }
      return rows.filter(r => keep.has(r));
    };
    const hookDedupe = cw => {
      const view = cw.cardsPane?.cardsList?.view;
      const Adapter = view?.constructor;
      if (!Adapter?.prototype?.sortBy || Adapter.prototype.__mcDedupe) {
        return;
      }
      const orig = Adapter.prototype.sortBy;
      Adapter.prototype.sortBy = function (column, direction, resort = false) {
        if (Services.prefs.getBoolPref(DEDUPE_PREF, true) && this._rowMap?.length) {
          const before = this._rowMap.length;
          this._rowMap = dedupeRows(this._rowMap);
          if (this._rowMap.length != before) {
            resort = true;
          }
        }
        return orig.call(this, column, direction, resort);
      };
      Adapter.prototype.__mcDedupe = true;
      this.restorers.push(() => {
        Adapter.prototype.sortBy = orig;
        delete Adapter.prototype.__mcDedupe;
      });

      // Labels je Kontakt: aus welchen Adressbüchern er stammt – nur in der
      // vereinigten Ansicht „Alle Adressbücher“
      const Row = cw.customElements.get("ab-card-row");
      // Kontaktkarten genau so hoch wie die Mailkarten (Thunderbird rechnet
      // die Liste mit ROW_HEIGHT, das Design übernimmt --mc-card-h)
      if (Row && !Object.getOwnPropertyDescriptor(Row, "ROW_HEIGHT")?.get) {
        const self = this;
        Object.defineProperty(Row, "ROW_HEIGHT", {
          configurable: true,
          get: () => self.mcCardHeight || 67,
          set: () => {},
        });
        cw.document.documentElement.style.setProperty("--mc-card-h", `${this.mcCardHeight || 67}px`);
        try {
          cw.cardsPane?.cardsList?.reset?.();
        } catch {}
        this.restorers.push(() => {
          delete Row.ROW_HEIGHT;
          Row.ROW_HEIGHT = 52;
        });
      }
      if (Row && !Row.prototype.__mcBooks) {
        const origFill = Row.prototype.fillRow;
        Row.prototype.fillRow = function (...args) {
          const result = origFill.apply(this, args);
          try {
            let box = this.querySelector(".mc-books");
            // Labels nur in „Alle Adressbücher“ und solange „Adressbuch“ im Menü angehakt ist
            const showBooks = cw.document.getElementById("sortContext")
              ?.querySelector('menuitem[value="addrbook"]')?.hasAttribute("checked") ?? true;
            const unified = cw.document.getElementById("books")?.selectedIndex == 0 && showBooks;
            const row = this.view?._rowMap?.[this._index];
            const sources = row?.mcSources?.length ? row.mcSources : [row?.directory?.dirName].filter(Boolean);
            if (!unified || !sources.length) {
              box?.remove();
            } else {
              if (!box) {
                box = cw.document.createElement("span");
                box.className = "mc-books";
                this.firstLine.appendChild(box);
              }
              box.replaceChildren(...sources.map(n => {
                const pill = cw.document.createElement("span");
                pill.className = "mc-book";
                pill.textContent = n;
                const c = accountColor(n);
                pill.style.setProperty("--c", c);
                pill.classList.toggle("mc-dark-color", textOnColor(c) == "#fff" && isVeryDark(c));
                return pill;
              }));
              box.title = sources.join(", ");
            }
          } catch (e) {
            log("book labels error", e);
          }
          return result;
        };
        Row.prototype.__mcBooks = true;
        this.restorers.push(() => {
          Row.prototype.fillRow = origFill;
          delete Row.prototype.__mcBooks;
        });
      }

      // Tabellenansicht: Thunderbirds Spalte „Adressbuch“ zeigt dieselben
      // Konto-Etiketten wie die Karten – bei zusammengeführten Kontakten alle
      // Bücher, nicht nur eines. Einmalig eingeblendet.
      const TableRow = cw.customElements.get("ab-table-card-row");
      if (TableRow && !TableRow.prototype.__mcBooks) {
        const origTableFill = TableRow.prototype.fillRow;
        TableRow.prototype.fillRow = function (...args) {
          const result = origTableFill.apply(this, args);
          try {
            const cell = this.querySelector(".addrbook-column");
            const row = this.view?._rowMap?.[this._index];
            const sources = row?.mcSources?.length ? row.mcSources : [row?.directory?.dirName].filter(Boolean);
            if (cell && !cell.hidden && sources.length) {
              const box = cw.document.createElement("span");
              box.className = "mc-books";
              box.replaceChildren(...sources.map(n => {
                const pill = cw.document.createElement("span");
                pill.className = "mc-book";
                pill.textContent = n;
                const c = accountColor(n);
                pill.style.setProperty("--c", c);
                pill.classList.toggle("mc-dark-color", textOnColor(c) == "#fff" && isVeryDark(c));
                return pill;
              }));
              cell.replaceChildren(box);
              cell.title = sources.join(", ");
            }
          } catch (e) {
            log("table labels error", e);
          }
          return result;
        };
        TableRow.prototype.__mcBooks = true;
        this.restorers.push(() => {
          TableRow.prototype.fillRow = origTableFill;
          delete TableRow.prototype.__mcBooks;
        });
        const COLUMN_PREF = "extensions.mailcards.abLabelColumn";
        const pane = cw.cardsPane;
        const abColumn = pane?.COLUMNS?.find(c => c.id == "addrbook");
        if (abColumn && !Services.prefs.getBoolPref(COLUMN_PREF, false)) {
          abColumn.hidden = false;
          const visible = pane.COLUMNS.filter(c => !c.hidden).map(c => c.id).join(",");
          Services.xulStore.setValue("about:addressbook", "cards", "columns", visible);
          try {
            pane.table.setColumns(pane.COLUMNS);
            pane.cardsList.reset?.();
          } catch {}
          Services.prefs.setBoolPref(COLUMN_PREF, true);
        }
      }

      // Schalter im Darstellungsmenü („…“ neben der Suche)
      const menu = cw.document.getElementById("sortContext");
      // Abschnittstitel, damit klar ist, dass „Anzeigename“ eine Auswahl ist
      if (menu && !menu.querySelector(".mc-caption")) {
        const de = Services.locale.appLocaleAsBCP47.startsWith("de");
        const caption = (label, before) => {
          if (!before) {
            return;
          }
          const c = cw.document.createXULElement("menucaption");
          c.className = "mc-caption";
          c.setAttribute("label", label);
          before.before(c);
          this.restorers.push(() => c.remove());
        };
        caption(de ? "Namen anzeigen als" : "Show Names As", menu.querySelector('menuitem[name="format"]'));
        caption(de ? "Sortieren" : "Sort", menu.querySelector('menuitem[name="sort"]'));
        caption(de ? "Ansicht" : "View", menu.querySelector('menuitem[value="addrbook"]'));
      }
      if (menu && !cw.document.getElementById("mcHideDuplicates")) {
        const de = Services.locale.appLocaleAsBCP47.startsWith("de");
        const sep = cw.document.createXULElement("menuseparator");
        const item = cw.document.createXULElement("menuitem");
        item.id = "mcHideDuplicates";
        item.setAttribute("type", "checkbox");
        item.setAttribute("label", de ? "Doppelte Kontakte zusammenführen" : "Merge Duplicate Contacts");
        if (Services.prefs.getBoolPref(DEDUPE_PREF, true)) {
          item.setAttribute("checked", "true");
        }
        item.addEventListener("command", () => {
          Services.prefs.setBoolPref(DEDUPE_PREF, item.hasAttribute("checked"));
          // Liste neu aufbauen (ausgeschaltet kommen die Doppelten zurück)
          cw.booksList?.dispatchEvent(new cw.CustomEvent("select"));
        });
        menu.append(sep, item);
        this.restorers.push(() => {
          sep.remove();
          item.remove();
        });
      }
      // aktuelle Liste sofort bereinigen
      cw.booksList?.dispatchEvent(new cw.CustomEvent("select"));
    };

    const styleContentPages = () => {
      markSearch();
      const uri = sheetURI();
      const tabmail = w.document.getElementById("tabmail");
      if (!uri || !tabmail) {
        return;
      }
      for (const tab of tabmail.tabInfo) {
        const cw = tab.browser?.contentWindow;
        const url = cw?.document?.documentURI || "";
        if (cw && url.startsWith("about:preferences")) {
          try {
            hookAppearanceChoice(cw);
          } catch (e) {
            log("appearance choice error", e);
          }
        }
        if (cw && url.startsWith("about:addressbook")) {
          try {
            hookAvatars(cw);
            hookBooksHeader(cw);
            hookSplitterReset(cw.document);
          } catch (e) {
            log("avatar fix error", e);
          }
          try {
            hookDedupe(cw);
            colorAccountRows(cw.document);
            cacheCardCount(cw.document);
          } catch (e) {
            log("dedupe error", e);
          }
        }
        if (!cw || !CONTENT_PAGES.test(url) || cw.__mcSheet == uri || cw.__mcTheme) {
          continue;
        }
        try {
          cw.windowUtils.loadSheetUsingURIString(uri, cw.windowUtils.USER_SHEET);
          cw.__mcSheet = uri;
        } catch (e) {
          log("content sheet error", url, e);
        }
      }
    };

    // Seitenleisten der übrigen Bereiche ein-/ausblenden wie die Ordnerliste
    // (Zustand je Bereich gespeichert, gleiche Animation wie in der Mail)
    const SIDE_PREF = "extensions.mailcards.hiddenSidebars";
    const SIDE_TOGGLE = {
      calendar: () => [w.document.getElementById("calSidebar"), w.document.getElementById("calsidebar_splitter")],
      tasks: () => [w.document.getElementById("calSidebar"), w.document.getElementById("calsidebar_splitter")],
      chat: () => [w.document.getElementById("listPaneBox"), w.document.getElementById("listSplitter")],
      addressBookTab: tab => {
        const doc = tab.browser?.contentDocument;
        return [doc?.getElementById("booksPane"), doc?.getElementById("booksSplitter")];
      },
      preferencesTab: tab => [tab.browser?.contentDocument?.getElementById("pref-category-box"), null],
      contentTab: tab => {
        const doc = tab.browser?.contentDocument;
        const url = doc?.documentURI || "";
        return url.startsWith("about:addons") ? [doc.getElementById("sidebar"), null]
          : url.startsWith("about:accountsettings") ? [doc.getElementById("accountTreeBox"), null]
          : [null, null];
      },
    };
    // Eine gemeinsame Breite für alle Seitenleisten: Wechselt man den Bereich,
    // bekommt dessen Seitenleiste dieselbe Breite – die Knöpfe springen nicht.
    // Zieht man eine Seitenleiste breiter/schmaler, gilt das für alle.
    const WIDTH_PREF = "extensions.mailcards.sidebarWidth";
    const sidebarFor = tab => {
      if (!tab) {
        return [null, null, null];
      }
      if (tab.mode?.name == "mail3PaneTab") {
        const ab = tab.chromeBrowser?.contentWindow;
        return [ab?.document?.getElementById("folderPane"), ab?.document?.getElementById("folderPaneSplitter"), ab];
      }
      const [el, splitter] = SIDE_TOGGLE[tab.mode?.name]?.(tab) || [];
      return [el, splitter, el?.ownerDocument?.defaultView];
    };
    const busy = (el, win) => !el || el.__mcAnimating || win?.__mcAnimating || el.classList.contains("mc-side-hidden");
    const applyCommonWidth = tab => {
      // (noch keine eigene Breite gespeichert: 206 px wie die Ordnerliste in Apple Mail)
      const W = Services.prefs.getIntPref(WIDTH_PREF, 0) || 206;
      const [el, splitter, win] = sidebarFor(tab);
      if (W < 160 || busy(el, win)) {
        return;
      }
      const current = el.getBoundingClientRect().width;
      if (!current || Math.abs(current - W) < 1.5) {
        return;
      }
      el.__mcSetting = Date.now();
      if (splitter?.localName == "hr" && "width" in splitter) {
        // Thunderbirds Pane-Splitter (Mail, Adressbuch) – speichert selbst
        splitter.width = W;
        splitter.dispatchEvent(new win.CustomEvent("splitter-resized", { bubbles: true }));
        // feste Breite aus der Ein-/Ausblend-Animation mitziehen
        if (el.style.getPropertyPriority("width") == "important") {
          el.style.setProperty("width", `${W}px`, "important");
        }
      } else {
        el.style.setProperty("width", `${W}px`, "important");
        if (splitter) {
          el.setAttribute("width", String(W));
          try {
            Services.xulStore.persist(el, "width");
          } catch {}
        }
      }
      // Toolbar-Kanten (Mail: Beginn der Knöpfe über der Nachricht) neu messen
      for (const ms of [50, 300, 700]) {
        w.setTimeout(() => {
          this.sideEdgeUpdaters?.forEach(fn => fn());
          this.offsetUpdaters?.forEach(fn => fn());
        }, ms);
      }
    };
    const watchWidth = tab => {
      const [el, splitter, win] = sidebarFor(tab);
      if (!el || el.__mcWidthWatch) {
        return;
      }
      el.__mcWidthWatch = true;
      // Startwert: die Breite der Ordnerliste in der Mail
      if (!Services.prefs.getIntPref(WIDTH_PREF, 0) && tab.mode?.name == "mail3PaneTab") {
        const width = Math.round(el.getBoundingClientRect().width);
        if (width >= 160) {
          Services.prefs.setIntPref(WIDTH_PREF, width);
        }
      }
      // Nur echtes Ziehen am Trenner zählt als neue Breite – übernommen erst
      // beim Loslassen und nie schmaler als 160 px (nicht das Einrichten der
      // Seite, Animationen oder Thunderbirds Mindestbreiten)
      if (splitter) {
        const onDown = () => {
          win.addEventListener("pointerup", () => win.setTimeout(() => {
            if (busy(el, win)) {
              return;
            }
            const width = Math.round(el.getBoundingClientRect().width);
            if (width >= 160 && Math.abs(width - Services.prefs.getIntPref(WIDTH_PREF, 0)) >= 2) {
              Services.prefs.setIntPref(WIDTH_PREF, width);
            }
          }, 300), { once: true });
        };
        splitter.addEventListener("pointerdown", onDown);
        this.restorers.push(() => splitter.removeEventListener("pointerdown", onDown));
      }
    };
    // Doppelklick auf eine Trennlinie stellt ihre Standardbreite wieder her:
    // Seitenleisten 206 px (gemeinsam), Mail-/Kontaktliste Thunderbirds
    // Standard (die andere Liste zieht mit), Today-Pane 280 px
    const hookSplitterReset = doc => {
      if (!doc || doc.__mcSplitterReset) {
        return;
      }
      doc.__mcSplitterReset = true;
      const SIDEBAR_SPLITTERS = new Set(["folderPaneSplitter", "booksSplitter", "calsidebar_splitter", "listSplitter"]);
      const onDblClick = event => {
        const splitter = event.target.closest?.("splitter, hr[is='pane-splitter'], [is='pane-splitter']");
        if (!splitter?.id) {
          return;
        }
        if (SIDEBAR_SPLITTERS.has(splitter.id)) {
          event.preventDefault();
          Services.prefs.clearUserPref(WIDTH_PREF);
          syncSidebarWidth();
        } else if (splitter.id == "messagePaneSplitter") {
          event.preventDefault();
          splitter.width = null;
          w.setTimeout(() => this.offsetUpdaters?.forEach(fn => fn()), 50);
        } else if (splitter.id == "sharedSplitter") {
          event.preventDefault();
          this.mcButtonsLeft = undefined; // nicht gleich wieder an die Mailliste angleichen
          splitter.width = null;
          w.setTimeout(() => {
            const cards = doc.getElementById("cardsPane")?.getBoundingClientRect();
            const tab = w.document.getElementById("tabmail")?.currentTabInfo;
            const b = tab?.browser?.getBoundingClientRect();
            if (cards?.width && b) {
              this.mcListWidth = Math.round(cards.width);
              this.mcButtonsLeft = b.left + cards.right + 6;
              this.mcListPending = true; // die Mailliste übernimmt die Kante
            }
            updateSideEdge();
          }, 50);
        } else if (splitter.id == "today-splitter") {
          event.preventDefault();
          const panel = doc.getElementById("today-pane-panel");
          if (panel) {
            panel.setAttribute("width", "280");
            panel.style.width = "280px";
            panel.setModeAttribute?.("modewidths", "280");
          }
        }
      };
      doc.addEventListener("dblclick", onDblClick, true);
      this.restorers.push(() => {
        doc.removeEventListener("dblclick", onDblClick, true);
        delete doc.__mcSplitterReset;
      });
    };

    const syncSidebarWidth = () => {
      const tabmail = w.document.getElementById("tabmail");
      const tab = tabmail?.currentTabInfo;
      const mail = tabmail?.tabInfo?.find(t => t.mode?.name == "mail3PaneTab");
      if (mail) {
        watchWidth(mail);
      }
      watchWidth(tab);
      applyCommonWidth(tab);
    };

    const sideState = () => {
      try {
        return JSON.parse(Services.prefs.getStringPref(SIDE_PREF, "{}"));
      } catch {
        return {};
      }
    };
    const currentSide = () => {
      const tab = w.document.getElementById("tabmail")?.currentTabInfo;
      const mode = tab?.mode?.name;
      const [el, splitter] = SIDE_TOGGLE[mode]?.(tab) || [];
      return { mode, el, splitter };
    };
    // Thunderbirds eigenes Zuklappen der Leiste (Trenner ganz nach links
    // gezogen) aufheben und abschalten – ein-/ausgeblendet wird über den
    // Seitenleisten-Knopf, sonst bliebe die Leiste nach dem Einblenden leer
    const unCollapse = (el, splitter) => {
      if (splitter?.localName == "splitter") {
        if (splitter.getAttribute("collapse") != "none") {
          splitter.setAttribute("collapse", "none");
        }
        if (splitter.getAttribute("state") == "collapsed") {
          splitter.setAttribute("state", "open");
        }
      }
      if (el?.getAttribute("collapsed") == "true") {
        el.removeAttribute("collapsed");
      }
    };
    const applySideState = () => {
      const { mode, el, splitter } = currentSide();
      if (!el || el.__mcAnimating) {
        return;
      }
      unCollapse(el, splitter);
      const hidden = !!sideState()[mode];
      el.classList.toggle("mc-side-hidden", hidden);
      splitter?.classList.toggle("mc-side-hidden", hidden);
    };
    this.sideHidden = () => {
      const { mode, el } = currentSide();
      return el ? !!sideState()[mode] : false;
    };
    this.toggleSpaceSidebar = () => {
      const { mode, el, splitter } = currentSide();
      if (!el || el.__mcAnimating) {
        return;
      }
      const win = el.ownerDocument.defaultView;
      const show = el.classList.contains("mc-side-hidden");
      const state = sideState();
      state[mode] = !show;
      // Kalender und Aufgaben teilen sich die Seitenleiste
      if (mode == "calendar" || mode == "tasks") {
        state.calendar = state.tasks = !show;
      }
      Services.prefs.setStringPref(SIDE_PREF, JSON.stringify(state));
      const DURATION = 250;
      const curve = cubicBezier(0.25, 0.1, 0.25, 1);
      unCollapse(el, splitter);
      if (show) {
        el.classList.remove("mc-side-hidden");
        splitter?.classList.remove("mc-side-hidden");
      }
      const full = el.getBoundingClientRect().width;
      if (!full) {
        return;
      }
      el.__mcAnimating = true;
      el.classList.add("mc-side-anim");
      // gespeicherte Breite der Leiste (Inline-Stil) merken und danach wiederherstellen
      const PROPS = ["overflow", "min-width", "width", "max-width"];
      const saved = PROPS.map(p => [p, el.style.getPropertyValue(p), el.style.getPropertyPriority(p)]);
      const kids = [...el.children];
      kids.forEach(k => k.style.setProperty("min-width", `${full}px`));
      el.style.setProperty("overflow", "hidden", "important");
      el.style.setProperty("min-width", "0px", "important");
      // Adressbuch: die Rasterspalte der Liste mitziehen, sonst bliebe die
      // Kontaktliste stehen und spränge erst am Ende
      const gridBody = el.id == "booksPane" ? el.ownerDocument.body : null;
      const savedColumn = gridBody?.style.getPropertyValue("--booksSplitter-width");
      const setW = v => {
        el.style.setProperty("width", `${v}px`, "important");
        el.style.setProperty("max-width", `${v}px`, "important");
        gridBody?.style.setProperty("--booksSplitter-width", `${v}px`);
      };
      if (show) {
        setW(0);
      }
      let start = null;
      const step = now => {
        if (start === null) {
          start = now;
        }
        const k = Math.min(1, (now - start) / DURATION);
        setW(full * (show ? curve(k) : 1 - curve(k)));
        updateSideEdge();
        if (k < 1) {
          win.requestAnimationFrame(step);
          return;
        }
        for (const [prop, value, prio] of saved) {
          if (value) {
            el.style.setProperty(prop, value, prio);
          } else {
            el.style.removeProperty(prop);
          }
        }
        kids.forEach(kid => kid.style.removeProperty("min-width"));
        if (gridBody) {
          if (savedColumn) {
            gridBody.style.setProperty("--booksSplitter-width", savedColumn);
          } else {
            gridBody.style.removeProperty("--booksSplitter-width");
          }
        }
        if (!show) {
          el.classList.add("mc-side-hidden");
          splitter?.classList.add("mc-side-hidden");
        }
        el.classList.remove("mc-side-anim");
        el.__mcAnimating = false;
        updateSideEdge();
        this.sidebarTip?.();
      };
      win.requestAnimationFrame(() => win.requestAnimationFrame(step));
    };

    // Suchfeld oben rechts: im Adressbuch filtert es die Kontakte, in den
    // Aufgaben die Aufgabenliste, in den Einstellungen die Einstellungen (statt der
    // Mail-Volltextsuche) – die Suchfelder in diesen Seiten entfallen.
    const SEARCH_TARGETS = {
      addressBookTab: {
        de: "Kontakte durchsuchen", en: "Search Contacts",
        input: cw => cw?.cardsPane?.searchInput,
        set: (input, text) => input.overrideSearchTerm(text), // löst dort selbst die Suche aus
      },
      tasks: {
        de: "Aufgaben durchsuchen", en: "Search Tasks",
        input: () => w.document.getElementById("task-text-filter-field"),
        set: (input, text) => {
          input.value = text;
          input.dispatchEvent(new w.Event("input", { bubbles: true }));
        },
      },
      preferencesTab: {
        de: "Einstellungen durchsuchen", en: "Find in Settings",
        input: cw => cw?.document.getElementById("searchInput"),
        set: (input, text) => {
          input.value = text;
          input.dispatchEvent(new input.ownerDocument.defaultView.Event("input", { bubbles: true }));
        },
      },
    };
    const currentTarget = () => {
      const tab = w.document.getElementById("tabmail")?.currentTabInfo;
      const target = SEARCH_TARGETS[tab?.mode?.name];
      return target ? { target, cw: tab.browser?.contentWindow } : null;
    };
    const abWindow = () => {
      const tab = w.document.getElementById("tabmail")?.currentTabInfo;
      return tab?.mode?.name == "addressBookTab" ? tab.browser?.contentWindow : null;
    };
    const globalSearch = () => w.document.querySelector("#unifiedToolbarContent global-search-bar");
    const syncSearchForTab = mode => {
      const bar = globalSearch();
      if (!bar) {
        return;
      }
      const target = SEARCH_TARGETS[mode];
      if (w.__mcSearchMode && w.__mcSearchMode != mode) {
        bar.reset(); // leert dabei auch die Suche der verlassenen Seite
      }
      w.__mcSearchMode = target ? mode : null;
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      if (target) {
        bar.setAttribute("placeholder", de ? target.de : target.en);
        const term = target.input(currentTarget()?.cw)?.value || "";
        bar.overrideSearchTerm?.(term);
      } else {
        bar.removeAttribute("placeholder");
      }
    };
    const hookSearchForwarding = () => {
      const content = w.document.getElementById("unifiedToolbarContent");
      if (!content || content.__mcSearchHook) {
        return;
      }
      content.__mcSearchHook = true;
      const forward = event => {
        if (!w.__mcSearchMode || event.target.localName != "global-search-bar") {
          return;
        }
        event.stopImmediatePropagation();
        event.preventDefault();
        const cur = currentTarget();
        const input = cur?.target.input(cur.cw);
        if (input && event.type == "autocomplete") {
          cur.target.set(input, event.detail || "");
        }
      };
      content.addEventListener("autocomplete", forward, true);
      content.addEventListener("search", forward, true);
      this.restorers.push(() => {
        content.removeEventListener("autocomplete", forward, true);
        content.removeEventListener("search", forward, true);
        delete content.__mcSearchHook;
      });
    };

    // Menüleiste → Help: „Halo Spaces …“ öffnet das Info-Fenster mit
    // Update-Prüfung, Feedback und „Danke sagen“.
    const hookHelpMenu = () => {
      const d = w.document;
      const popup = d.getElementById("menu_HelpPopup");
      if (!popup || d.getElementById("mcHaloSpaces")) {
        return;
      }
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      const sep = d.createXULElement("menuseparator");
      sep.id = "mcCheckUpdatesSeparator";
      const item = d.createXULElement("menuitem");
      item.id = "mcHaloSpaces";
      item.setAttribute("label", "halo.spaces …");
      item.addEventListener("command", () => this.openHaloWindow(w));
      const anchor = d.getElementById("aboutName");
      popup.insertBefore(sep, anchor);
      popup.insertBefore(item, anchor);
      this.restorers.push(() => {
        sep.remove();
        item.remove();
      });
    };

    // Gibt es oben das Suchfeld? (fehlt, wenn die globale Suche/Indexierung
    // aus ist oder es aus der Toolbar entfernt wurde) – nur dann blendet
    // userChrome.css die Suchfelder in Einstellungen, Adressbuch, Aufgaben aus
    const markSearch = () => {
      const has = !!w.document.querySelector('#unifiedToolbarContent > li[item-id="search-bar"]');
      w.document.documentElement.toggleAttribute("mc-search", has);
      for (const tab of w.document.getElementById("tabmail")?.tabInfo || []) {
        tab.browser?.contentDocument?.documentElement?.toggleAttribute("mc-search", has);
      }
    };
    const markTab = () => {
      hookSearchForwarding();
      hookHelpMenu();
      this.hideTodayPaneInChatOnce(w);
      styleContentPages();
      applySideState();
      w.setTimeout(applySideState, 400);
      w.setTimeout(applySideState, 1500);
      w.setTimeout(styleContentPages, 400);
      w.setTimeout(styleContentPages, 1500);
      const mode = w.document.getElementById("tabmail")?.currentTabInfo?.mode?.name;
      w.document.documentElement.toggleAttribute(
        "mc-mail",
        mode == "mail3PaneTab" || mode == "mailMessageTab"
      );
      w.document.documentElement.setAttribute("mc-tab", mode || "");
      markSearch();
      if (mode == "calendar") {
        w.document.getElementById("month-view")?.__mcMoreRefresh?.();
      }
      syncSearchForTab(mode);
      this.updateListHeader(w);
      syncSidebarWidth();
      w.setTimeout(syncSidebarWidth, 400); // Inhalte (Adressbuch …) evtl. später
      updateSideEdge();
      // Inhalt (Adressbuch, Einstellungen) ist evtl. erst später aufgebaut
      w.setTimeout(updateSideEdge, 300);
      w.setTimeout(updateSideEdge, 1200);
      // Tab-Leiste erscheint/verschwindet mit dem zweiten Tab → Kanten neu messen
      w.setTimeout(() => this.offsetUpdaters?.forEach(fn => fn()), 50);
    };
    // Esc in Einstellungen, Kalender, Adressbuch usw. schließt diesen Tab und
    // führt zurück zur vorherigen Ansicht (die Tab-Leiste ist ausgeblendet).
    const MAIL_MODES = new Set(["mail3PaneTab", "mailMessageTab"]);
    const onEscape = event => {
      if (event.key != "Escape" || event.defaultPrevented ||
          event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      const tabmail = w.document.getElementById("tabmail");
      const tab = tabmail?.currentTabInfo;
      if (!tab || MAIL_MODES.has(tab.mode?.name) || tabmail.tabInfo.length < 2) {
        return;
      }
      // Konto einrichten nicht versehentlich mit Esc verwerfen
      if (/^about:accountsetup/.test(tab.browser?.currentURI?.spec || "")) {
        return;
      }
      // Text in einem Eingabefeld: Esc leert zuerst nur das Feld
      const target = event.composedTarget || event.target;
      if (target && /^(input|textarea)$/i.test(target.localName) && target.value) {
        return;
      }
      // offenes Menü oder Dialog: Esc schließt zuerst diesen
      const doc = target?.ownerDocument;
      if (doc?.querySelector("menupopup[open], panel[open], dialog[open]") ||
          w.document.querySelector("menupopup[open], panel[open]")) {
        return;
      }
      event.preventDefault();
      tabmail.closeTab(tab);
    };
    const hooked = new WeakSet();
    const hookEscape = () => {
      const tabmail = w.document.getElementById("tabmail");
      const targets = [w];
      for (const tab of tabmail?.tabInfo || []) {
        const cw = (tab.browser || tab.chromeBrowser)?.contentWindow;
        if (cw) {
          targets.push(cw);
        }
      }
      for (const target of targets) {
        if (!hooked.has(target)) {
          hooked.add(target);
          target.addEventListener("keydown", onEscape);
          this.restorers.push(() => target.removeEventListener("keydown", onEscape));
        }
      }
    };

    // Seitenleisten-Knopf wie Apple Mail: blendet nur die Ordnerliste aus/ein
    // (statt das Bereiche-Menü zu öffnen). Außerhalb der Mailansicht führt er
    // zurück zur Mail. Bereiche bleiben über ⌃1–⌃5 erreichbar.
    const toggleSidebar = () => {
      const tabmail = w.document.getElementById("tabmail");
      const tab = tabmail?.currentTabInfo;
      if (tab?.mode?.name == "mail3PaneTab") {
        const ab = tab.chromeBrowser?.contentWindow;
        const splitter = ab?.paneLayout?.folderPaneSplitter;
        if (splitter) {
          this.animateSidebar(ab, splitter);
        }
      } else {
        // in allen anderen Bereichen deren Seitenleiste ein-/ausblenden
        this.toggleSpaceSidebar?.();
      }
    };
    const hookSidebarButton = () => {
      const button = w.document.getElementById("spacesPinnedButton");
      if (!button || button.dataset.mcSidebar) {
        return;
      }
      button.dataset.mcSidebar = "1";
      const popup = button.querySelector("menupopup");
      const blockPopup = event => event.preventDefault();
      const onPress = event => {
        if (event.type == "mousedown" && event.button != 0) {
          return;
        }
        if (event.type == "keydown" && event.key != "Enter" && event.key != " ") {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        toggleSidebar();
      };
      popup?.addEventListener("popupshowing", blockPopup);
      button.addEventListener("mousedown", onPress, true);
      button.addEventListener("keydown", onPress, true);
      // Tooltip je nach Zustand: „Hide Sidebar“ bzw. „Show Sidebar“
      const oldTooltip = button.getAttribute("tooltiptext");
      const updateTip = () => {
        const de = Services.locale.appLocaleAsBCP47.startsWith("de");
        const tab = w.document.getElementById("tabmail")?.currentTabInfo;
        let text;
        if (tab?.mode?.name == "mail3PaneTab") {
          const collapsed = tab.chromeBrowser?.contentWindow?.paneLayout?.folderPaneSplitter?.isCollapsed;
          text = collapsed
            ? (de ? "Seitenleiste einblenden" : "Show Sidebar")
            : (de ? "Seitenleiste ausblenden" : "Hide Sidebar");
        } else {
          text = this.sideHidden?.()
            ? (de ? "Seitenleiste einblenden" : "Show Sidebar")
            : (de ? "Seitenleiste ausblenden" : "Hide Sidebar");
        }
        button.setAttribute("tooltiptext", text);
      };
      updateTip();
      this.sidebarTip = updateTip; // nach der Animation erneut aufrufen
      button.addEventListener("mouseenter", updateTip);
      this.restorers.push(() => {
        popup?.removeEventListener("popupshowing", blockPopup);
        button.removeEventListener("mousedown", onPress, true);
        button.removeEventListener("keydown", onPress, true);
        button.removeEventListener("mouseenter", updateTip);
        delete button.dataset.mcSidebar;
        if (oldTooltip) {
          button.setAttribute("tooltiptext", oldTooltip);
        } else {
          button.removeAttribute("tooltiptext");
        }
      });
    };

    // Bereiche-Leiste ein-/ausblenden: eigener kleiner Knopf unten links
    // (statt Thunderbirds Knopf in der Leiste), mit derselben Animation wie
    // die Ordnerliste. Funktioniert unabhängig davon, ob die Ordner sichtbar sind.
    const hookSpacesToggle = () => {
      const d = w.document;
      const bar = d.getElementById("spacesToolbar");
      if (!bar || !w.gSpacesToolbar || d.getElementById("mcSpacesToggle")) {
        return;
      }
      const btn = d.createElementNS("http://www.w3.org/1999/xhtml", "button");
      btn.id = "mcSpacesToggle";
      btn.type = "button";
      // Tooltip je nach Zustand: „Hide Spaces“ bzw. „Show Spaces“
      const updateTip = () => {
        const de = Services.locale.appLocaleAsBCP47.startsWith("de");
        const label = w.gSpacesToolbar.isHidden
          ? (de ? "Bereiche einblenden" : "Show Spaces")
          : (de ? "Bereiche ausblenden" : "Hide Spaces");
        btn.title = label;
        btn.setAttribute("aria-label", label);
      };
      updateTip();
      btn.addEventListener("mouseenter", updateTip);
      btn.addEventListener("click", () => this.animateSpaces(w, updateTip));
      bar.after(btn); // Geschwister der Leiste, damit CSS ihren Zustand sieht
      this.restorers.push(() => btn.remove());
    };

    // Today-Pane ein-/ausblenden: Knopf unten rechts (Gegenstück zum
    // Bereiche-Knopf unten links) statt des ✕ oben in der Today-Pane
    const hookTodayToggle = () => {
      const d = w.document;
      const panel = d.getElementById("today-pane-panel");
      const command = d.getElementById("calendar_toggle_todaypane_command");
      if (!command || d.getElementById("mcTodayToggle")) {
        return;
      }
      const btn = d.createElementNS("http://www.w3.org/1999/xhtml", "button");
      btn.id = "mcTodayToggle";
      btn.type = "button";
      const updateTip = () => {
        const de = Services.locale.appLocaleAsBCP47.startsWith("de");
        const shown = !!w.TodayPane?.isVisible;
        const label = shown
          ? (de ? "Heute-Leiste ausblenden" : "Hide Today Pane")
          : (de ? "Heute-Leiste einblenden" : "Show Today Pane");
        btn.title = label;
        btn.setAttribute("aria-label", label);
        btn.toggleAttribute("data-shown", shown);
      };
      updateTip();
      btn.addEventListener("mouseenter", updateTip);
      btn.addEventListener("click", () => this.animateTodayPane(w, command, updateTip));
      const mo = panel ? new w.MutationObserver(() => {
        updateTip();
        this.todayTopSync?.();
      }) : null;
      mo?.observe(panel, { attributes: true, attributeFilter: ["collapsed", "hidden", "collapsedinmodes"] });
      // in die Toolbar-Zeile; darüber reicht die Today-Pane bis ganz oben
      // (#mcTodayTop in ihrer Breite) – wie die Seitenleiste links
      const row = d.getElementById("unifiedToolbarContainer");
      const top = d.createElementNS("http://www.w3.org/1999/xhtml", "div");
      top.id = "mcTodayTop";
      // Überschrift „Today Pane“ oben in der Toolbar-Zeile, neben dem Knopf
      const title = d.createElementNS("http://www.w3.org/1999/xhtml", "span");
      title.id = "mcTodayTitle";
      title.textContent = Services.locale.appLocaleAsBCP47.startsWith("de") ? "Heute-Leiste" : "Today Pane";
      top.append(title);
      row?.prepend(top);
      (row || d.body).append(btn);
      // Breite der Today-Pane (0, wenn aus) an die Toolbar-Zeile – Suchfeld,
      // Fläche und Knopf richten sich danach, auch während der Animation
      const sync = () => {
        if (!row) {
          return;
        }
        const width = panel && w.TodayPane?.isVisible ? Math.round(panel.getBoundingClientRect().width) : 0;
        setVar(row, "--mc-tp-w", `${width}px`);
        setVar(row, "--mc-caption-w", `${captionWidth(d)}px`);
      };
      this.todayTopSync = sync;
      const ro = panel ? new w.ResizeObserver(sync) : null;
      ro?.observe(panel);
      sync();
      this.restorers.push(() => {
        mo?.disconnect();
        ro?.disconnect();
        btn.remove();
        top.remove();
        row?.style.removeProperty("--mc-tp-w");
        delete this.todayTopSync;
      });
    };

    // Titel und Anzahl über der Mailliste in der Toolbar-Zeile, rechts davon
    // Filter und „…“ in einer Kapsel – wie Apple Mail. Thunderbirds eigene
    // Kopfzeile in der Liste wird per CSS ausgeblendet.
    const hookListHeader = () => {
      const d = w.document;
      const row = d.getElementById("unifiedToolbarContainer");
      if (!row || d.getElementById("mcListHeader")) {
        return;
      }
      const X = "http://www.w3.org/1999/xhtml";
      const el = (tag, cls) => {
        const e = d.createElementNS(X, tag);
        if (cls) e.className = cls;
        return e;
      };
      const box = el("div");
      box.id = "mcListHeader";
      const text = el("div", "mc-lh-text");
      const title = el("div", "mc-lh-title");
      const count = el("div", "mc-lh-count");
      text.append(title, count);
      const tools = el("div", "mc-lh-tools");
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      const filter = el("button", "mc-lh-filter");
      filter.title = de ? "Schnellfilter" : "Quick Filter";
      const more = el("button", "mc-lh-more");
      more.title = de ? "Darstellung der Liste" : "Message List Display Options";
      tools.append(filter, more);
      box.append(text, tools);
      const ab = () => d.getElementById("tabmail")?.currentAbout3Pane;
      filter.addEventListener("click", () => ab()?.goDoCommand("cmd_toggleQuickFilterBar"));
      more.addEventListener("click", () => {
        const cw = abWindow();
        const popup = cw
          ? cw.document.getElementById("sortContext")
          : ab()?.document.getElementById("threadPaneDisplayContext");
        const r = more.getBoundingClientRect();
        popup?.openPopupAtScreen(w.mozInnerScreenX + r.left, w.mozInnerScreenY + r.bottom + 4, false);
      });
      row.append(box);
      this.restorers.push(() => box.remove());
      this.updateListHeader(w);
    };

    // Terminspalte rechts im Stil von Fastmail, in unserem Design:
    // Minikalender oben, darunter Monatstitel und Agenda mit Wochentag und
    // großer Tageszahl links, Termine als Farbblöcke rechts.
    // Monatsansicht wie Apple Kalender: passen nicht alle Termine in einen
    // Tag, steht unten „+N weitere“ – ein Klick öffnet den Tag in der
    // Tagesansicht. Dazu Zoom per Trackpad (Pinch) oder ⌘/Ctrl + Mausrad:
    // höhere Wochenzeilen, die Monatsansicht wird dann scrollbar.
    const ZOOM_PREF = "extensions.mailcards.monthZoom";
    const hookMonthView = () => {
      const d = w.document;
      const mv = d.getElementById("month-view");
      if (!mv || mv.__mcMore) {
        return;
      }
      mv.__mcMore = true;
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      // Höhe der Monatstabelle in Pixeln: sichtbare Höhe × Zoom (eine
      // Prozentangabe greift in der scrollbaren Ansicht nicht mehr)
      const applyHeight = () => {
        const table = mv.querySelector("table.monthtable");
        const z = parseFloat(mv.style.getPropertyValue("--mc-month-zoom")) || 1;
        if (!table) {
          return;
        }
        if (z <= 1.01) {
          table.style.removeProperty("height");
          return;
        }
        const visible = mv.clientHeight - (table.getBoundingClientRect().top - mv.getBoundingClientRect().top - mv.scrollTop);
        table.style.setProperty("height", `${Math.round(Math.max(200, visible) * z)}px`, "important");
      };
      const setZoom = z => {
        const zoom = Math.max(1, Math.min(3, Math.round(z * 100) / 100));
        mv.style.setProperty("--mc-month-zoom", zoom);
        mv.toggleAttribute("mc-zoomed", zoom > 1.01);
        applyHeight();
        Services.prefs.setStringPref(ZOOM_PREF, String(zoom));
        return zoom;
      };
      let zoom = setZoom(parseFloat(Services.prefs.getStringPref(ZOOM_PREF, "1")) || 1);
      let pending = false;
      const update = () => {
        pending = false;
        for (const box of mv.querySelectorAll("calendar-month-day-box")) {
          const list = box.querySelector(".calendar-month-day-box-list");
          let more = box.querySelector(":scope > .mc-more");
          if (!list) {
            continue;
          }
          const lr = list.getBoundingClientRect();
          const items = [...list.children];
          // Platz für die Zeile „+N weitere“ freihalten, sobald etwas fehlt
          for (const i of items) {
            i.removeAttribute("data-mc-cut");
          }
          let cut = [];
          if (items.some(i => i.getBoundingClientRect().bottom > lr.bottom + 1)) {
            cut = items.filter(i => i.getBoundingClientRect().bottom > lr.bottom - 18);
          }
          const hidden = cut.length;
          for (const i of cut) {
            i.setAttribute("data-mc-cut", "true");
          }
          if (!hidden) {
            more?.remove();
            box.removeAttribute("mc-has-more");
            continue;
          }
          if (!more) {
            more = d.createElementNS("http://www.w3.org/1999/xhtml", "button");
            more.className = "mc-more";
            more.addEventListener("click", event => {
              event.stopPropagation();
              const date = box.date;
              if (date) {
                w.switchToView?.("day");
                w.currentView?.()?.goToDay?.(date);
              }
            });
            more.addEventListener("dblclick", event => event.stopPropagation());
            box.appendChild(more);
          }
          box.setAttribute("mc-has-more", "true");
          more.textContent = de ? `+${hidden} weitere` : `+${hidden} more`;
        }
      };
      // nur messen, wenn der Kalender vorne ist – sonst liefe das bei jeder
      // Größenänderung (z. B. Ein-/Ausblend-Animation in der Mail) mit
      let dirty = false;
      const visible = () => w.document.getElementById("tabmail")?.currentTabInfo?.mode?.name == "calendar";
      const schedule = () => {
        if (!visible() || w.__mcSpacesAnimating) {
          dirty = true;
          return;
        }
        if (!pending) {
          pending = true;
          w.requestAnimationFrame(update);
        }
      };
      mv.__mcMoreRefresh = () => {
        if (dirty) {
          dirty = false;
          schedule();
        }
      };
      const mo = new w.MutationObserver(records => {
        // eigene Änderungen (die „+N“-Knöpfe) lösen keine neue Runde aus
        if (records.some(r => ![...r.addedNodes, ...r.removedNodes].every(n => n.classList?.contains("mc-more")) || r.type == "attributes")) {
          schedule();
        }
      });
      mo.observe(mv, { childList: true, subtree: true });
      const ro = new w.ResizeObserver(() => {
        schedule();
      });
      ro.observe(mv);
      const table = mv.querySelector("table.monthtable");
      if (table) {
        ro.observe(table);
      }
      // Fenstergröße geändert: Tabellenhöhe neu berechnen
      const outer = new w.ResizeObserver(() => applyHeight());
      outer.observe(mv.parentElement || mv);
      // Zoom: Pinch-Geste auf dem Trackpad und ⌘/Ctrl + Mausrad
      const onGesture = event => {
        zoom = setZoom(zoom * (1 + (event.delta || 0) / 100));
        event.preventDefault();
        schedule();
      };
      const onWheel = event => {
        if (!(event.ctrlKey || event.metaKey)) {
          return;
        }
        event.preventDefault();
        zoom = setZoom(zoom * (event.deltaY < 0 ? 1.08 : 1 / 1.08));
        schedule();
      };
      // Mausrad blättert immer den Monat – Thunderbird gibt es sonst an einen
      // Tag weiter, dessen Einträge nicht ganz hineinpassen (der scrollt dann
      // unsichtbar in sich, und das Blättern scheint zu hängen); verborgene
      // Einträge zeigt „+N weitere“
      let pixels = 0;
      let lastWheel = -Infinity;
      let lastDir = 0;
      const onMonthWheel = event => {
        if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey || mv.hasAttribute("mc-zoomed") ||
            !Services.prefs.getBoolPref("calendar.view.mousescroll", true)) {
          return;
        }
        event.stopPropagation();
        event.preventDefault();
        // Jede Raste blättert sofort einen Monat (macOS liefert eine Raste als
        // weiche Folge kleiner Schritte, zusammen ~100 px – Thunderbirds
        // Schwelle von 150 px verschluckte sie). Innerhalb einer Folge
        // (Abstand < 150 ms) erst nach weiteren 200 px den nächsten Monat –
        // schnelles Drehen und das Trackpad blättern so weiter.
        let delta = 0;
        if (!event.deltaY) {
          return;
        }
        const now = event.timeStamp;
        const dir = Math.sign(event.deltaY);
        if (event.deltaMode != event.DOM_DELTA_PIXEL) {
          delta = dir;
        } else if (now - lastWheel > 150 || dir != lastDir) {
          delta = dir;
          pixels = 0;
        } else {
          pixels += event.deltaY;
          if (Math.abs(pixels) >= 200) {
            delta = dir;
            pixels = 0;
          }
        }
        lastWheel = now;
        lastDir = dir;
        if (delta) {
          mv.moveView(delta);
        }
      };
      mv.addEventListener("wheel", onMonthWheel, { capture: true, passive: false });
      this.restorers.push(() => mv.removeEventListener("wheel", onMonthWheel, { capture: true }));
      mv.addEventListener("MozMagnifyGestureUpdate", onGesture);
      mv.addEventListener("MozMagnifyGesture", onGesture);
      mv.addEventListener("wheel", onWheel, { passive: false });
      this.restorers.push(() => {
        mo.disconnect();
        ro.disconnect();
        outer.disconnect();
        mv.querySelector("table.monthtable")?.style.removeProperty("height");
        mv.removeEventListener("MozMagnifyGestureUpdate", onGesture);
        mv.removeEventListener("MozMagnifyGesture", onGesture);
        mv.removeEventListener("wheel", onWheel);
        for (const el of mv.querySelectorAll(".mc-more")) {
          el.remove();
        }
        mv.style.removeProperty("--mc-month-zoom");
        mv.removeAttribute("mc-zoomed");
        delete mv.__mcMore;
      });
      schedule();
    };

    const decorateAgenda = () => {
      const d = w.document;
      const agenda = d.getElementById("agenda");
      if (!agenda || agenda.__mcAgenda) {
        return;
      }
      agenda.__mcAgenda = true;
      // einmalig: Minikalender statt Mini-Tagesanzeige in allen Bereichen und
      // eine breitere Spalte (beides über ▾-Menü bzw. Ziehen änderbar)
      const ONCE = "extensions.mailcards.todayPaneLayout";
      if (!Services.prefs.getBoolPref(ONCE, false)) {
        try {
          const panel = d.getElementById("today-pane-panel");
          const modes = (panel.getAttribute("mode") || "").split(",").filter(Boolean);
          const all = modes.join(",");
          d.getElementById("today-minimonth-box")?.setAttribute("collapsedinmodes", "");
          d.getElementById("mini-day-box")?.setAttribute("collapsedinmodes", all);
          d.getElementById("today-none-box")?.setAttribute("collapsedinmodes", all);
          panel.setAttribute("modewidths", modes.map(() => "280").join(","));
          panel.style.width = "280px";
          for (const id of ["today-minimonth-box", "mini-day-box", "today-none-box", "today-pane-panel"]) {
            const el = d.getElementById(id);
            for (const attr of ["collapsedinmodes", "modewidths"]) {
              if (el?.hasAttribute(attr)) {
                Services.xulStore.setValue(d.documentURI, id, attr, el.getAttribute(attr));
              }
            }
          }
          w.TodayPane?.displayMiniSection("minimonth");
          Services.prefs.setBoolPref(ONCE, true);
        } catch (e) {
          log("today pane layout error", String(e).slice(0, 160));
        }
      }
      const locale = Services.locale.appLocaleAsBCP47;
      const wdFmt = new Intl.DateTimeFormat(locale, { weekday: "short" });
      const monthFmt = new Intl.DateTimeFormat(locale, { month: "long" });
      const X = "http://www.w3.org/1999/xhtml";
      const title = d.createElementNS(X, "div");
      title.id = "mcAgendaTitle";
      // ‹  Monat Jahr  › – blättert monatsweise; die Liste zeigt die Termine
      // des gezeigten Monats (im aktuellen Monat ab heute)
      const de = locale.startsWith("de");
      const mkChevron = (cls, label, dir) => {
        const b = d.createElementNS(X, "button");
        b.className = `mc-agenda-nav ${cls}`;
        b.type = "button";
        b.title = label;
        b.setAttribute("aria-label", label);
        b.addEventListener("click", () => this.shiftAgendaMonth(w, dir));
        return b;
      };
      const label = d.createElementNS(X, "span");
      label.className = "mc-agenda-month";
      title.append(
        mkChevron("mc-prev", de ? "Voriger Monat" : "Previous Month", -1),
        label,
        mkChevron("mc-next", de ? "Nächster Monat" : "Next Month", 1)
      );
      agenda.before(title);
      this.hookAgendaMonthRange(w);
      const apply = () => {
        const today = new Date();
        const todayKey = `${today.getFullYear()}${String(today.getMonth() + 1).padStart(2, "0")}${String(today.getDate()).padStart(2, "0")}`;
        let firstDate = null;
        for (const li of agenda.querySelectorAll(":scope > li.agenda-listitem")) {
          const key = li.dateString || "";
          if (key.length >= 8) {
            const date = new Date(+key.slice(0, 4), +key.slice(4, 6) - 1, +key.slice(6, 8));
            firstDate ??= date;
            const header = li.querySelector(".agenda-date-header");
            if (header) {
              header.dataset.mcWd = wdFmt.format(date).replace(/\.$/, "");
              header.dataset.mcDay = String(date.getDate());
              header.toggleAttribute("data-mc-today", key.slice(0, 8) == todayKey);
            }
          }
          // bald beginnend (in den nächsten 3 Stunden): Zusatz „in 2 hr“ zeigen
          try {
            const start = li.item?.startDate;
            const begins = start && !start.isDate ? start.nativeTime / 1000 - Date.now() : Infinity;
            li.toggleAttribute("data-mc-soon", begins > 0 && begins <= 3 * 3600 * 1000);
          } catch {}
          // Kalenderfarbe für den Farbblock
          const dot = li.querySelector(".agenda-listitem-calendar");
          const details = li.querySelector(".agenda-listitem-details");
          let color = dot ? w.getComputedStyle(dot).backgroundColor : "";
          if ((!color || color == "rgba(0, 0, 0, 0)") && details) {
            color = details.style.backgroundColor || w.getComputedStyle(details).backgroundColor;
          }
          if (color && color != "rgba(0, 0, 0, 0)") {
            li.style.setProperty("--mc-c", color);
          }
        }
        // Monat der Liste (Starttag der Today-Pane), sonst des ersten Termins
        let date = firstDate || today;
        try {
          const start = w.TodayPane?.start;
          if (start) {
            date = new Date(start.year, start.month, start.day);
          }
        } catch {}
        const month = monthFmt.format(date);
        label.replaceChildren(
          Object.assign(d.createElementNS(X, "b"), { textContent: month }),
          d.createTextNode(` ${date.getFullYear()}`)
        );
      };
      let pending = false;
      const mo = new w.MutationObserver(() => {
        if (!pending) {
          pending = true;
          w.requestAnimationFrame(() => {
            pending = false;
            apply();
          });
        }
      });
      mo.observe(agenda, { childList: true, subtree: true, characterData: true });
      apply();
      this.restorers.push(() => {
        mo.disconnect();
        title.remove();
        delete agenda.__mcAgenda;
      });
    };

    // Kalender und Aufgaben: ein „+“ wie in Apple Kalender – fragt in einem
    // Menü nach Termin oder Aufgabe (der zweite Knopf ist per CSS ausgeblendet)
    const hookNewButton = () => {
      const d = w.document;
      const bar = d.querySelector("unified-toolbar");
      if (!bar || bar.__mcNewHooked) {
        return;
      }
      bar.__mcNewHooked = true;
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      // Popover wie in Apple Kalender: zwei runde Symbole mit Beschriftung
      const popup = d.createXULElement("panel");
      popup.id = "mcNewPopup";
      popup.setAttribute("type", "arrow");
      popup.setAttribute("noautofocus", "true");
      const NS = "http://www.w3.org/1999/xhtml";
      const box = d.createElementNS(NS, "div");
      box.className = "mc-pop";
      const ICONS = {
        // Kalenderblatt mit Uhr
        event: '<rect x="3.5" y="5" width="15" height="13.5" rx="2.4"/><path d="M3.5 9.2h15M7.6 3.2v3.2M14.4 3.2v3.2"/><circle cx="17.6" cy="17.6" r="4.4" fill="var(--mc-pop-icon-bg)"/><path d="M17.6 15.6v2.2l1.4 0.9"/>',
        // Liste mit abgehaktem und offenem Punkt
        task: '<circle cx="6" cy="7.5" r="2.4"/><path d="M4.9 7.5l0.8 0.8 1.4-1.6"/><circle cx="6" cy="16.5" r="2.4"/><path d="M11 7.5h9M11 16.5h9"/>',
      };
      for (const [id, label, icon, command] of [
        ["mcNewEvent", de ? "Neuer Termin" : "New Event", "event", "calendar_new_event_command"],
        ["mcNewTask", de ? "Neue Aufgabe" : "New Task", "task", "calendar_new_todo_command"],
      ]) {
        const btn = d.createElementNS(NS, "button");
        btn.id = id;
        btn.className = "mc-pop-item";
        const circle = d.createElementNS(NS, "span");
        circle.className = "mc-pop-icon";
        circle.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[icon]}</svg>`;
        const text = d.createElementNS(NS, "span");
        text.className = "mc-pop-label";
        text.textContent = label;
        btn.append(circle, text);
        btn.addEventListener("click", () => {
          popup.hidePopup();
          w.goDoCommand(command);
        });
        box.append(btn);
      }
      popup.append(box);
      (d.getElementById("mainPopupSet") || d.documentElement).append(popup);
      const onClick = event => {
        const li = event.target.closest?.('li[item-id="new-event"]');
        const mode = d.getElementById("tabmail")?.currentTabInfo?.mode?.name;
        if (!li || (mode != "calendar" && mode != "tasks")) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        // im Kalender gleich ein neuer Termin, in den Aufgaben gleich eine
        // neue Aufgabe (die Auswahl gibt es über das „+“ der Today-Pane)
        w.goDoCommand(mode == "tasks" ? "calendar_new_todo_command" : "calendar_new_event_command");
      };
      bar.addEventListener("click", onClick, true);
      // dasselbe Popover über einem Knopf unten (Today-Pane): nach oben, mittig
      this.openNewPopupAbove = anchor => {
        if (popup.state == "open" || popup.state == "showing") {
          popup.hidePopup();
          return;
        }
        popup.classList.add("mc-up");
        const width = 294; // Breite des Popovers samt Rand für den Schatten
        popup.openPopup(anchor, "before_start", Math.round(anchor.getBoundingClientRect().width / 2 - width / 2), 12);
      };
      const onHidden = () => popup.classList.remove("mc-up");
      popup.addEventListener("popuphidden", onHidden);
      this.restorers.push(() => {
        bar.removeEventListener("click", onClick, true);
        popup.removeEventListener("popuphidden", onHidden);
        popup.remove();
        delete bar.__mcNewHooked;
        delete this.openNewPopupAbove;
      });
    };

    // Today-Pane: Titel „Today Pane“ (statt „Termine“/„Aufgaben“) und der Knopf
    // „Neuer Termin“ gleich rechts daneben in der Kopfzeile
    const hookTodayPaneHeader = () => {
      const d = w.document;
      const header = d.getElementById("today-pane-header");
      const button = d.getElementById("todaypane-new-event-button");
      if (!header || header.dataset.mcTitle) {
        return;
      }
      header.dataset.mcTitle = Services.locale.appLocaleAsBCP47.startsWith("de") ? "Heute-Leiste" : "Today Pane";
      const home = button?.parentElement;
      const next = button?.nextSibling;
      // ganz unten in der Today-Pane, unter den Einträgen: ein „+“ wie im
      // Kalender, das nach Termin oder Aufgabe fragt
      const panel = d.getElementById("today-pane-panel");
      const savedCommand = button?.getAttribute("command");
      const onPlus = event => {
        event.preventDefault();
        event.stopPropagation();
        this.openNewPopupAbove?.(button);
      };
      if (button && panel) {
        panel.append(button);
        button.removeAttribute("command");
        button.addEventListener("click", onPlus);
      }
      this.restorers.push(() => {
        delete header.dataset.mcTitle;
        if (button && home) {
          button.removeEventListener("click", onPlus);
          if (savedCommand) {
            button.setAttribute("command", savedCommand);
          }
          home.insertBefore(button, next);
        }
      });
    };

    // „Heute“ in der Sprache der Oberfläche (Thunderbird hat dafür nur einen Tooltip)
    const labelToday = () => {
      const btn = w.document.getElementById("todayViewButton");
      if (!btn || btn.dataset.mcLabel) {
        return;
      }
      let text = "Today";
      try {
        text = new Intl.RelativeTimeFormat(Services.locale.appLocaleAsBCP47, { numeric: "auto" }).format(0, "day");
        text = text.charAt(0).toLocaleUpperCase(Services.locale.appLocaleAsBCP47) + text.slice(1);
      } catch {}
      btn.dataset.mcLabel = text;
    };

    // Kalender-Titel wie in Apple Kalender: Monat fett, Jahreszahl dünn
    const hookTitle = () => {
      const el = w.document.getElementById("intervalDescription");
      if (!el || el.__mcTitle) {
        return;
      }
      el.__mcTitle = true;
      const split = () => {
        if (el.querySelector(".mc-year")) {
          return;
        }
        const m = el.textContent.match(/^(.*\S)(\s+)(\d{4})\s*$/s);
        if (!m) {
          return;
        }
        const year = w.document.createElement("span");
        year.className = "mc-year";
        year.textContent = m[3];
        el.replaceChildren(m[1] + m[2], year);
      };
      const mo = new w.MutationObserver(split);
      mo.observe(el, { childList: true, characterData: true, subtree: true });
      split();
      this.restorers.push(() => {
        mo.disconnect();
        el.textContent = el.textContent;
        delete el.__mcTitle;
      });
    };

    // Tag und Woche: Cmd + Mausrad (oder Zwei-Finger-Zoom) ändert wie
    // Cmd+Plus/Minus den Stundenabstand
    const hookMultidayZoom = () => {
      for (const id of ["day-view", "week-view"]) {
        const view = w.document.getElementById(id);
        if (!view || view.__mcZoom || typeof view.zoomIn != "function") {
          continue;
        }
        view.__mcZoom = true;
        let acc = 0;
        const STEP = 40; // Pixel Mausrad pro Zoomstufe
        const zoom = delta => {
          acc += delta;
          while (Math.abs(acc) >= STEP) {
            // wie Cmd+Plus/Minus: nach oben = größer (weniger Stunden sichtbar)
            if (acc < 0) {
              view.zoomOut();
              acc += STEP;
            } else {
              view.zoomIn();
              acc -= STEP;
            }
          }
        };
        const onWheel = event => {
          if (!event.metaKey && !event.ctrlKey) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          const px = event.deltaMode == 1 ? event.deltaY * 16 : event.deltaMode == 2 ? event.deltaY * 400 : event.deltaY;
          zoom(px);
        };
        const onGesture = event => {
          event.preventDefault();
          zoom(-event.delta * 2);
        };
        view.addEventListener("wheel", onWheel, { passive: false, capture: true });
        view.addEventListener("MozMagnifyGestureUpdate", onGesture);
        this.restorers.push(() => {
          view.removeEventListener("wheel", onWheel, { capture: true });
          view.removeEventListener("MozMagnifyGestureUpdate", onGesture);
          delete view.__mcZoom;
        });
      }
    };

    const scan = () => {
      markTab();
      decorateAgenda();
      hookMonthView();
      hookMultidayZoom();
      hookNewButton();
      hookTitle();
      labelToday();
      hookTodayPaneHeader();
      hookEscape();
      hookSidebarButton();
      hookSpacesToggle();
      hookTodayToggle();
      hookSplitterReset(w.document);
      hookListHeader();
      this.updateListHeader(w);
      this.styleSearch(w);
      const tabmail = w.document.getElementById("tabmail");
      for (const tab of tabmail?.tabInfo || []) {
        const cw = tab.chromeBrowser?.contentWindow;
        if (cw && cw.location?.href == "about:3pane") {
          hookSplitterReset(cw.document);
          this.patch(cw, 0);
        }
      }
    };
    scan();
    let runs = 0;
    const interval = w.setInterval(() => {
      scan();
      if (++runs >= 30) {
        w.clearInterval(interval);
      }
    }, 1000);
    const monitor = {
      monitorName: "mail-cards",
      onTabOpened: () => w.setTimeout(scan, 300),
      onTabSwitched: () => {
        markTab();
        scan();
        w.setTimeout(hookEscape, 800); // Inhalt des neuen Tabs ist evtl. erst jetzt geladen
      },
      onTabTitleChanged() {},
      onTabClosing() {},
      onTabPersist() {},
      onTabRestored() {},
    };
    const attach = () => {
      const tabmail = w.document.getElementById("tabmail");
      if (tabmail?.registerTabMonitor) {
        tabmail.registerTabMonitor(monitor);
        this.restorers.push(() => tabmail.unregisterTabMonitor(monitor));
      } else {
        w.setTimeout(attach, 500);
      }
    };
    attach();
    w.addEventListener("unload", () => this.mainWindows.delete(w), { once: true });
    this.restorers.push(() => w.document.documentElement.removeAttribute("mc-mail"));
    this.restorers.push(() => w.document.documentElement.removeAttribute("mc-tab"));
    this.restorers.push(() => w.clearInterval(interval));
  }

  // Suchfeld wie Apple Mail: Lupe links, Platzhalter nur „Search“/„Suchen“
  // (ohne „…“ und ohne ⌘+K-Hinweis). Liegt im Shadow-DOM, daher hier statt CSS.
  styleSearch(w) {
    const bar = w.document.querySelector("global-search-bar");
    if (!bar?.shadowRoot || bar.shadowRoot.getElementById("mail-cards-search")) {
      return;
    }
    const style = w.document.createElementNS("http://www.w3.org/1999/xhtml", "style");
    style.id = "mail-cards-search";
    style.textContent = `
      .button { inset-inline-start: 4px !important; inset-inline-end: auto !important; }
      input { padding-inline: 30px 10px !important; }
      div { inset-inline-start: 30px !important; inset-inline-end: 10px !important; }
    `;
    bar.shadowRoot.appendChild(style);

    const placeholder = bar.querySelector('[slot="placeholder"]');
    const l10nId = placeholder?.getAttribute("data-l10n-id");
    if (placeholder) {
      placeholder.removeAttribute("data-l10n-id");
      placeholder.textContent = Services.locale.appLocaleAsBCP47.startsWith("de")
        ? "Suchen"
        : "Search";
    }
    this.restorers.push(() => {
      style.remove();
      if (placeholder && l10nId) {
        placeholder.setAttribute("data-l10n-id", l10nId);
        w.document.l10n?.translateElements([placeholder]);
      }
    });
  }

  // Ordnerliste ein-/ausblenden wie in Apple Mail: die Ordnerliste bleibt
  // stehen, Mailliste und Mail schieben sich mit ihrer linken Kante nach links
  // darüber und decken sie zu (beim Einblenden umgekehrt). Dauer und Kurve sind die macOS-Standardwerte für
  // Seitenleisten: 0,25 s, cubic-bezier(0.25, 0.1, 0.25, 1).
  // Thunderbird steuert die Breite über --folderPaneSplitter-width am Raster.
  animateSidebar(ab, splitter) {
    if (ab.__mcAnimating) {
      return;
    }
    const pane = ab.document.getElementById("folderPane");
    const grid = splitter.parentNode;
    const prop = "--folderPaneSplitter-width";
    const DURATION = 250;
    const curve = cubicBezier(0.25, 0.1, 0.25, 1);
    const collapsing = !splitter.isCollapsed;
    let full;
    if (collapsing) {
      full = pane.getBoundingClientRect().width;
    } else {
      splitter.isCollapsed = false;
      full = pane.getBoundingClientRect().width;
    }
    if (!full) {
      return;
    }
    const saved = grid.style.getPropertyValue(prop);
    const inner = [...pane.children];
    // Inhalt der Ordnerliste behält seine volle Breite und bleibt stehen –
    // er wird nur von rechts her zugedeckt
    inner.forEach(el => (el.style.minWidth = `${full}px`));
    pane.style.overflow = "hidden";
    pane.style.minWidth = "0px"; // Thunderbirds Mindestbreite (100 px) würde die Animation stoppen
    pane.classList.add("mc-side-anim"); // (auch unsere 160 px)
    // Der Teiler fixiert die Ordnerliste beim Ändern der Fenstergröße mit
    // „width: …px !important“ – das hält sonst das Raster fest
    const lockedWidth = pane.style.getPropertyValue("width");
    pane.style.removeProperty("width");
    let relocked = false;
    ab.__mcAnimating = true;
    // Die Uhr läuft erst ab dem ersten gezeichneten Bild: beim Einblenden baut
    // Thunderbird die Ordnerliste zuerst neu auf, das würde sonst den Anfang
    // der Bewegung verschlucken und sie ruckartig starten lassen
    let start = null;
    const step = now => {
      if (start === null) {
        start = now;
      }
      const k = Math.min(1, (now - start) / DURATION);
      // setzt Thunderbird währenddessen eine neue Sperre, gilt sie dem
      // Zwischenstand – entfernen und am Ende durch die volle Breite ersetzen
      if (pane.style.getPropertyPriority("width") == "important") {
        relocked = true;
        pane.style.removeProperty("width");
      }
      const shown = collapsing ? 1 - curve(k) : curve(k); // sichtbarer Anteil 1 → 0 bzw. 0 → 1
      const width = full * shown;
      grid.style.setProperty(prop, `${width}px`);
      this.offsetUpdaters?.forEach(fn => fn());
      if (k < 1) {
        ab.requestAnimationFrame(step);
        return;
      }
      inner.forEach(el => (el.style.minWidth = ""));
      pane.style.overflow = "";
      pane.style.minWidth = "";
      pane.classList.remove("mc-side-anim");
      if ((lockedWidth || relocked) && !collapsing) {
        pane.style.setProperty("width", `${full}px`, "important");
      }
      if (collapsing) {
        splitter.isCollapsed = true; // setzt die Variable selbst auf 0px
      } else if (saved) {
        grid.style.setProperty(prop, saved);
      } else {
        grid.style.removeProperty(prop);
      }
      ab.__mcAnimating = false;
      this.sidebarTip?.();
      ab.setTimeout(() => this.offsetUpdaters?.forEach(fn => fn()), 30);
    };
    // erstes Bild sofort setzen, damit nichts aufblitzt
    if (!collapsing) {
      grid.style.setProperty(prop, "0px");
      pane.getBoundingClientRect(); // Aufbau der Ordnerliste jetzt erzwingen, nicht im ersten Bild
    }
    ab.requestAnimationFrame(() => ab.requestAnimationFrame(step));
  }

  // Titel und Anzahl der Kopfzeile aus dem aktuellen Mail-Tab übernehmen
  updateListHeader(w) {
    const d = w.document;
    const box = d.getElementById("mcListHeader");
    const tab = d.getElementById("tabmail")?.currentTabInfo;
    if (box && tab?.mode?.name == "addressBookTab") {
      this.updateAbHeader(box, tab.browser?.contentWindow);
      return;
    }
    const ab = d.getElementById("tabmail")?.currentAbout3Pane;
    if (!box || !ab?.document) {
      return;
    }
    const title = box.querySelector(".mc-lh-title");
    const count = box.querySelector(".mc-lh-count");
    try {
      const folder = ab.gFolder;
      title.textContent = folder ? appleFolderTitle(folder) : ab.document.title || "";
      const n = folder?.getTotalMessages(false) || ab.gDBView?.numMsgsInView || 0;
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      count.textContent = folder || ab.gDBView
        ? `${n.toLocaleString(Services.locale.appLocaleAsBCP47)} ${de ? (n == 1 ? "E-Mail" : "E-Mails") : (n == 1 ? "message" : "messages")}`
        : "";
    } catch (e) {
      log("list header error", e);
    }
  }

  // Kopfzeile über der Kontaktliste: gewähltes Adressbuch und Anzahl der
  // (sichtbaren) Kontakte; aktualisiert sich bei Auswahl und Suche.
  updateAbHeader(box, cw) {
    const title = box.querySelector(".mc-lh-title");
    const count = box.querySelector(".mc-lh-count");
    const books = cw?.booksList;
    const list = cw?.cardsPane?.cardsList;
    if (!books || !list) {
      return;
    }
    if (!cw.__mcHeaderHook) {
      cw.__mcHeaderHook = true;
      const update = () => cw.setTimeout(() => this.updateAbHeader(box, cw), 0);
      books.addEventListener("select", update);
      cw.cardsPane.searchInput?.addEventListener("autocomplete", update);
      new cw.MutationObserver(update).observe(list, { childList: true, subtree: true });
    }
    try {
      const row = books.getRowAtIndex?.(books.selectedIndex) || books.selectedRow;
      const name = row?.querySelector(".bookRow-name, .listRow-name, span")?.textContent || row?.textContent || "";
      title.textContent = name.trim();
      const n = list.view?.rowCount ?? 0;
      const de = Services.locale.appLocaleAsBCP47.startsWith("de");
      count.textContent = `${n.toLocaleString(Services.locale.appLocaleAsBCP47)} ${de ? (n == 1 ? "Kontakt" : "Kontakte") : (n == 1 ? "contact" : "contacts")}`;
    } catch (e) {
      log("ab header error", e);
    }
  }

  // Bereiche-Leiste wie die Ordnerliste animieren: Breite 0 ↔ 67 px über
  // --mc-spaces-w (userChrome.css leitet --spaces-total-width davon ab), die
  // Leiste schiebt sich dabei von links herein bzw. hinaus.
  animateSpaces(w, onDone) {
    const spaces = w.gSpacesToolbar;
    const root = w.document.documentElement;
    if (!spaces || w.__mcSpacesAnimating) {
      return;
    }
    const FULL = 67;
    const DURATION = 250;
    const curve = cubicBezier(0.25, 0.1, 0.25, 1);
    const showing = spaces.isHidden;
    // Die Breite nicht als Variable am Wurzelelement ändern – das ließe
    // Thunderbird pro Bild alle ~5000 Elemente des Fensters neu durchrechnen
    // (~20 ms, die Animation ruckelt). Stattdessen direkt an den fünf
    // Elementen, die sich bewegen; am Ende wieder entfernen.
    const d = w.document;
    const bar = d.getElementById("spacesToolbar");
    const body = d.getElementById("messengerBody");
    const title = d.getElementById("titlebar");
    const row = d.getElementById("unifiedToolbarContainer");
    const toggle = d.getElementById("mcSpacesToggle");
    const set = v => {
      const px = `${v}px`;
      bar?.style.setProperty("--spaces-total-width", px);
      toggle?.style.setProperty("--spaces-total-width", px);
      if (body) {
        body.style.marginInlineStart = px;
      }
      if (title) {
        title.style.marginInlineStart = px;
      }
      if (row) {
        row.style.inlineSize = `calc(100vw - ${px})`;
      }
    };
    const clear = () => {
      bar?.style.removeProperty("--spaces-total-width");
      toggle?.style.removeProperty("--spaces-total-width");
      body?.style.removeProperty("margin-inline-start");
      title?.style.removeProperty("margin-inline-start");
      row?.style.removeProperty("inline-size");
    };
    w.__mcSpacesAnimating = true;
    if (showing) {
      set(0);
      spaces.toggleToolbar(false);
      root.getBoundingClientRect(); // Aufbau jetzt erzwingen, nicht im ersten Bild
    }
    let start = null;
    const step = now => {
      if (start === null) {
        start = now;
      }
      const k = Math.min(1, (now - start) / DURATION);
      set(FULL * (showing ? curve(k) : 1 - curve(k)));
      if (k < 1) {
        w.requestAnimationFrame(step);
        return;
      }
      if (!showing) {
        spaces.toggleToolbar(true);
      }
      clear();
      root.style.removeProperty("--mc-spaces-w");
      w.__mcSpacesAnimating = false;
      onDone?.();
      const realign = () => {
        this.offsetUpdaters?.forEach(fn => fn());
        this.sideEdgeUpdaters?.forEach(fn => fn());
      };
      realign();
      w.setTimeout(realign, 30);
    };
    w.requestAnimationFrame(() => w.requestAnimationFrame(step));
  }

  // Terminliste der Today-Pane: vom Starttag bis zum Monatsende (statt einer
  // festen Anzahl Tage) – passt zum Monat im Titel
  hookAgendaMonthRange(w) {
    const agenda = w.TodayPane?.agenda;
    if (!agenda || agenda.__mcMonthRange) {
      return;
    }
    agenda.__mcMonthRange = true;
    Object.defineProperty(agenda, "numberOfDays", {
      configurable: true,
      get() {
        try {
          const start = this.startDate || w.TodayPane.start;
          const last = new Date(start.year, start.month + 1, 0).getDate();
          return Math.max(1, last - start.day + 1);
        } catch {
          return 14;
        }
      },
    });
    // Thunderbird zeigt für andere Tage als heute nur diesen einen Tag –
    // hier immer vom Starttag bis zum Monatsende
    agenda.update = async function (date) {
      this.startDate = date.clone();
      this.startDate.isDate = true;
      this.endDate = this.startDate.clone();
      this.endDate.day += this.numberOfDays;
      this.itemType = Ci.calICalendar.ITEM_FILTER_TYPE_EVENT;
      if (this.isActive) {
        await this.refreshItems();
      } else {
        await this.ensureInitialized();
      }
      this.selectedIndex = 0;
    };
    try {
      w.TodayPane.updatePeriod();
    } catch {}
    this.restorers.push(() => {
      delete agenda.update;
      Object.defineProperty(agenda, "numberOfDays", {
        configurable: true,
        get: () => Services.prefs.getIntPref("calendar.agenda.days", 14),
      });
      delete agenda.__mcMonthRange;
      try {
        w.TodayPane.updatePeriod();
      } catch {}
    });
  }

  // Monat der Today-Pane wechseln: aktueller Monat ab heute, sonst ab dem 1.
  shiftAgendaMonth(w, dir) {
    try {
      const { cal } = ChromeUtils.importESModule("resource:///modules/calendar/calUtils.sys.mjs");
      const start = w.TodayPane.start;
      const target = new Date(start.year, start.month + dir, 1);
      const now = new Date();
      const day = target.getFullYear() == now.getFullYear() && target.getMonth() == now.getMonth()
        ? now : target;
      const dt = cal.dtz.jsDateToDateTime(new Date(day.getFullYear(), day.getMonth(), day.getDate()), cal.dtz.defaultTimezone);
      dt.isDate = true;
      w.TodayPane.setDay(dt);
    } catch (e) {
      log("agenda month error", String(e).slice(0, 160));
    }
  }

  // Today-Pane weich ein-/ausblenden wie die Seitenleisten: die Breite
  // gleitet zwischen 0 und voller Breite, der Inhalt behält seine Breite und
  // wird nur zugedeckt
  animateTodayPane(w, command, onDone) {
    const d = w.document;
    const panel = d.getElementById("today-pane-panel");
    if (!panel || panel.__mcAnimating) {
      return;
    }
    const showing = !w.TodayPane?.isVisible;
    if (showing) {
      command.doCommand();
    }
    const full = panel.getBoundingClientRect().width;
    if (!full) {
      if (!showing) {
        command.doCommand();
      }
      onDone?.();
      return;
    }
    panel.__mcAnimating = true;
    const DURATION = 250;
    const curve = cubicBezier(0.25, 0.1, 0.25, 1);
    const PROPS = ["overflow", "min-width", "width", "max-width"];
    const saved = PROPS.map(p => [p, panel.style.getPropertyValue(p), panel.style.getPropertyPriority(p)]);
    const kids = [...panel.children];
    kids.forEach(k => k.style.setProperty("min-width", `${full}px`));
    panel.style.setProperty("overflow", "hidden", "important");
    panel.style.setProperty("min-width", "0px", "important");
    const setW = v => {
      panel.style.setProperty("width", `${v}px`, "important");
      panel.style.setProperty("max-width", `${v}px`, "important");
    };
    if (showing) {
      setW(0);
    }
    let start = null;
    const step = now => {
      if (start === null) {
        start = now;
      }
      const k = Math.min(1, (now - start) / DURATION);
      setW(full * (showing ? curve(k) : 1 - curve(k)));
      this.todayTopSync?.();
      if (k < 1) {
        w.requestAnimationFrame(step);
        return;
      }
      for (const [prop, value, prio] of saved) {
        if (value) {
          panel.style.setProperty(prop, value, prio);
        } else {
          panel.style.removeProperty(prop);
        }
      }
      kids.forEach(k2 => k2.style.removeProperty("min-width"));
      if (!showing) {
        command.doCommand();
      }
      panel.__mcAnimating = false;
      this.todayTopSync?.();
      onDone?.();
    };
    w.requestAnimationFrame(() => w.requestAnimationFrame(step));
  }

  applyToolbarOnce() {
    if (Services.prefs.getBoolPref(TOOLBAR_PREF, false)) {
      return; // spätere eigene Änderungen an der Toolbar bleiben erhalten
    }
    try {
      const { getState, storeState } = ChromeUtils.importESModule(
        "resource:///modules/CustomizationState.mjs"
      );
      // nur, wenn die Mail-Toolbar noch auf Thunderbirds Standard steht –
      // eigene Anordnungen und Knöpfe anderer Add-ons bleiben erhalten
      const state = getState();
      if (!state.mail) {
        storeState({ ...state, mail: APPLE_TOOLBAR });
        Services.prefs.setIntPref("toolbar.unifiedtoolbar.buttonstyle", 2); // nur Symbole
      }
      Services.prefs.setBoolPref(TOOLBAR_PREF, true);
    } catch (e) {
      log("toolbar error", e);
    }
  }

  // Einmalig die übrigen Bereiche belegen – nur Bereiche, die noch auf
  // Thunderbirds Standard stehen; eigene Anpassungen bleiben erhalten.
  applySpaceToolbarsOnce() {
    if (Services.prefs.getBoolPref(SPACE_TOOLBAR_PREF, false)) {
      return;
    }
    try {
      const { getState, storeState } = ChromeUtils.importESModule(
        "resource:///modules/CustomizationState.mjs"
      );
      const state = { ...getState() };
      for (const [space, items] of Object.entries(SPACE_TOOLBARS)) {
        if (!state[space]) {
          state[space] = items;
        }
      }
      storeState(state);
      Services.prefs.setBoolPref(SPACE_TOOLBAR_PREF, true);
    } catch (e) {
      log("space toolbar error", e);
    }
  }

  // Die Toolbar-Knöpfe sollen – wie in Apple Mail – genau über der linken
  // Kante der geöffneten Mail beginnen. Die Breite der Spalten davor wird
  // als CSS-Variable ans Hauptfenster gegeben (userChrome.css nutzt sie).
  trackToolbarOffset(win) {
    const top = win.browsingContext?.topChromeWindow;
    const threadPane = win.document.getElementById("threadPane");
    if (!top || !threadPane) {
      return;
    }
    // Thunderbird sperrt die Ordnerliste zeitweise mit „width: …px !important“
    // (Teiler „resize-lock-ids“). Wird diese Sperre in einem ungünstigen Moment
    // gesetzt (z. B. mitten in einer Animation), bleibt die Liste schmaler als
    // ihre Spalte und rechts davon entsteht eine weiße Lücke. Dann die Sperre
    // auf die echte Spaltenbreite korrigieren.
    const fixFolderLock = () => {
      const splitter = win.paneLayout?.folderPaneSplitter;
      const pane = win.document.getElementById("folderPane");
      if (!splitter || !pane || splitter.isCollapsed || win.__mcAnimating) {
        return;
      }
      if (pane.style.getPropertyPriority("width") != "important") {
        return;
      }
      const column = parseFloat(win.getComputedStyle(splitter.parentNode).gridTemplateColumns);
      const locked = parseFloat(pane.style.getPropertyValue("width"));
      if (Number.isFinite(column) && column > 0 && Math.abs(column - locked) > 1) {
        log("folder lock fixed", { locked, column });
        pane.style.setProperty("width", `${column}px`, "important");
      }
    };
    // Die Mailliste lässt sich nur so weit nach rechts ziehen, dass Knöpfe
    // und Suchfeld rechts davon Platz haben (wie in Apple Mail) – Thunderbirds
    // Teiler kennt kein Maximum, daher hier die kleinste Breite der Nachricht
    const minMessageWidth = () => {
      const pane = win.document.getElementById("messagePane");
      const browser = win.browsingContext.embedderElement;
      const row = top.document.getElementById("unifiedToolbarContainer");
      if (!pane || !browser || !row || !win.document.body.classList.contains("layout-vertical")) {
        return 0;
      }
      const msgRight = browser.getBoundingClientRect().left + pane.getBoundingClientRect().right;
      const want = toolbarNeed(top.document) - (row.getBoundingClientRect().right - msgRight);
      // die Liste selbst nie schmaler als 240 px machen
      const list = threadPane.getBoundingClientRect();
      const room = pane.getBoundingClientRect().right - list.left - 240;
      return Math.max(0, Math.min(want, room));
    };
    const msgSplitter = win.document.getElementById("messagePaneSplitter");
    if (msgSplitter && typeof msgSplitter._updateSize == "function" && !msgSplitter.__mcClamp) {
      msgSplitter.__mcClamp = true;
      const origUpdate = msgSplitter._updateSize;
      msgSplitter._updateSize = function (size) {
        return origUpdate.call(this, typeof size == "number" ? Math.max(size, minMessageWidth()) : size);
      };
      this.restorers.push(() => {
        msgSplitter._updateSize = origUpdate;
        delete msgSplitter.__mcClamp;
      });
    }
    const enforceMessageWidth = () => {
      if (!msgSplitter || msgSplitter.isCollapsed || win.__mcAnimating || top.__mcSpacesAnimating ||
          msgSplitter.resizeElement?.id != "messagePane") {
        return;
      }
      const min = minMessageWidth();
      const pane = win.document.getElementById("messagePane");
      if (min && pane.getBoundingClientRect().width < min - 1) {
        msgSplitter.width = Math.ceil(min);
      }
    };
    const update = () => {
      const content = top.document.getElementById("unifiedToolbarContent");
      const browser = win.browsingContext.embedderElement;
      if (!content || !browser || win.closed || top.__mcSpacesAnimating) {
        return;
      }
      enforceMessageWidth();
      // nur der Mail-Tab, der gerade vorne ist, richtet die Toolbar aus –
      // sonst überschreibt ein zweiter Mail-Tab im Hintergrund die Kanten
      // (auch nicht, solange ein anderer Bereich vorne ist)
      const current = top.document.getElementById("tabmail")?.currentTabInfo;
      if (current?.chromeBrowser != browser) {
        return;
      }
      fixFolderLock();
      // im Adressbuch neu gezogene Listenbreite übernehmen
      if (this.mcListPending && msgSplitter && !msgSplitter.isCollapsed && msgSplitter.resizeElement?.id == "messagePane") {
        const listNow = threadPane.getBoundingClientRect().width;
        const pane = win.document.getElementById("messagePane");
        if (listNow > 1 && this.mcButtonsLeft) {
          this.mcListPending = false;
          // rechte Listenkante auf die im Adressbuch gezogene Stelle
          const browserLeft = win.browsingContext.embedderElement.getBoundingClientRect().left;
          const diff = browserLeft + threadPane.getBoundingClientRect().right - (this.mcButtonsLeft - 6);
          if (Math.abs(diff) >= 1) {
            msgSplitter.width = Math.max(minMessageWidth(), Math.round(pane.getBoundingClientRect().width + diff));
          }
        }
      }
      // Ohne sichtbare Mailliste (z. B. Kontoübersicht) bleiben die Knöpfe
      // dort, wo sie in der Mailansicht zuletzt standen.
      const listRect = threadPane.getBoundingClientRect();
      const folderRect = win.document.getElementById("folderPane")?.getBoundingClientRect();
      let listRight;
      if (listRect.width > 1) {
        listRight = listRect.right;
        this.lastListRight = listRight - (folderRect?.right || 0); // Breite der Mailliste merken
      } else {
        listRight = (folderRect?.right || 0) + (this.lastListRight ?? 0);
      }
      const paneRight = browser.getBoundingClientRect().left + listRight;
      // für die übrigen Bereiche merken: dort beginnen die Knöpfe an derselben
      // Stelle, und die Kontaktliste im Adressbuch ist so breit wie die Mailliste
      this.mcButtonsLeft = paneRight + 6;
      if (listRect.width > 1) {
        this.mcListWidth = Math.round(listRect.width);
      }
      // Bezug ist der Anfang des ersten Abstandhalters (die Toolbar hat
      // eigenen Innenabstand); +6 px wie der Einzug in Apple Mail.
      const start = (content.querySelector(':scope > li[item-id="spacer"]') || content).getBoundingClientRect().left;
      let offset = Math.max(0, Math.round(paneRight - start + 6));
      // nie links vom Seitenleisten-Knopf beginnen
      const toggle = top.document.getElementById("spacesPinnedButton");
      const tb = toggle?.getBoundingClientRect();
      if (tb && tb.width) {
        offset = Math.max(offset, Math.round(tb.right - start + 12));
      }
      setBarVar(top.document, "--mc-toolbar-offset", `${offset}px`);
      const animating = top.__mcSpacesAnimating || win.__mcAnimating;
      // Suchfeld in jedem Bereich gleich breit (333 px wie Apple Mail): fehlt
      // dafür Platz, wird zuerst der Abstand nach „Verfassen“ kleiner (69 → 12 px)
      const write = content.querySelector(':scope > li[item-id="write-message"]');
      const search = content.querySelector(':scope > li[item-id="search-bar"]');
      // (nicht während einer Ein-/Ausblend-Animation – das kostet pro Bild ein
      // komplettes Neuberechnen; am Ende wird einmal gemessen)
      if (!animating && write && search && write.getBoundingClientRect().width) {
        const spacer = search.previousElementSibling;
        const gap = parseFloat(top.getComputedStyle(write).marginInlineEnd) || 0;
        const spare = (spacer?.getAttribute("item-id") == "spacer" ? spacer.getBoundingClientRect().width : 0) -
          (333 - search.getBoundingClientRect().width);
        const next = Math.max(12, Math.min(69, Math.round(gap + spare)));
        if (Math.abs(next - gap) >= 1) {
          setBarVar(top.document, "--mc-write-gap", `${next}px`);
        }
      }
      // Rechte Kante der Ordnerliste relativ zur Toolbar-Zeile: damit färbt
      // userChrome.css die Seitenleiste bis ganz nach oben grau wie in Apple Mail.
      const folderPane = win.document.getElementById("folderPane");
      const row = top.document.getElementById("unifiedToolbarContainer");
      if (folderPane && row) {
        const fr = folderPane.getBoundingClientRect();
        const right = fr.width
          ? browser.getBoundingClientRect().left + fr.right - row.getBoundingClientRect().left
          : 0;
        setBarVar(top.document, "--mc-sidebar-right", `${Math.max(0, Math.round(right))}px`
        );
        // rechte Kante der Mailliste für die Trennlinie in der Toolbar-Zeile
        // Ist das Fenster für alle Knöpfe zu schmal, schrumpft der Einzug davor –
        // die Kopfzeile über der Liste endet dann vor dem ersten Knopf
        const firstSpacer = content.querySelector(':scope > li[item-id="spacer"]');
        const buttonsStart = firstSpacer ? firstSpacer.getBoundingClientRect().right : paneRight;
        const rowLeft = row.getBoundingClientRect().left;
        // Trennlinie an der echten Kante der Mailliste; reicht der Platz nicht
        // und die Knöpfe beginnen schon links davon, entfällt sie in der
        // Toolbar-Zeile (statt versetzt quer durch die Knöpfe zu laufen)
        const listRight = buttonsStart >= paneRight - 2 ? paneRight - rowLeft : -10;
        setBarVar(top.document, "--mc-lh-right", `${Math.round(Math.min(paneRight, buttonsStart - 6) - rowLeft)}px`);
        setBarVar(top.document, "--mc-list-right", `${Math.round(listRight)}px`
        );
        // Die Tab-Leiste kann weiter rechts beginnen (z. B. neben der
        // Bereiche-Leiste) – dort dieselben Kanten, um den Versatz korrigiert.
        const tabs = top.document.getElementById("tabs-toolbar");
        if (tabs) {
          const shift = tabs.getBoundingClientRect().left - row.getBoundingClientRect().left;
          setVar(tabs, "--mc-sidebar-right", `${Math.max(0, Math.round(right - shift))}px`);
          setVar(tabs, "--mc-list-right", `${Math.round(listRight - shift)}px`);
        }
      }
    };
    this.offsetUpdaters ??= new Set();
    this.offsetUpdaters.add(update);
    const ro = new win.ResizeObserver(update);
    ro.observe(threadPane);
    const fp = win.document.getElementById("folderPane");
    if (fp) {
      ro.observe(fp);
    }
    // Ordnerliste ein-/ausgeklappt: sofort neu ausrichten (ein eingeklapptes
    // Element meldet der ResizeObserver nicht zuverlässig)
    const splitterEl = win.document.getElementById("folderPaneSplitter");
    const onSplitter = () => win.setTimeout(update, 0);
    for (const type of ["splitter-collapsed", "splitter-expanded", "splitter-resized"]) {
      splitterEl?.addEventListener(type, onSplitter);
    }
    this.restorers.push(() => {
      for (const type of ["splitter-collapsed", "splitter-expanded", "splitter-resized"]) {
        splitterEl?.removeEventListener(type, onSplitter);
      }
    });
    ro.observe(win.document.documentElement);
    update();
    this.restorers.push(() => {
      ro.disconnect();
      this.offsetUpdaters?.delete(update);
      const tabsBar = top.document.getElementById("tabs-toolbar");
      tabsBar?.style.removeProperty("--mc-sidebar-right");
      tabsBar?.style.removeProperty("--mc-list-right");
      barTarget(top.document).style.removeProperty("--mc-toolbar-offset");
      barTarget(top.document).style.removeProperty("--mc-sidebar-right");
      barTarget(top.document).style.removeProperty("--mc-list-right");
      barTarget(top.document).style.removeProperty("--mc-lh-right");
    });
  }

  // Eigene Symbole statt Thunderbirds --icon-*-Grafiken. Die SVGs nutzen
  // context-stroke/-fill (Farbe vom Element) – das erlauben nur chrome:// und
  // resource://, deshalb resource://mailcards/ auf die Erweiterung zeigen lassen
  // und icon-vars.css als Benutzer-Stylesheet für alle Dokumente anmelden.
  registerIconVars() {
    if (!extensionRoot) {
      return;
    }
    const res = Services.io.getProtocolHandler("resource").QueryInterface(Ci.nsIResProtocolHandler);
    res.setSubstitution("mailcards", extensionRoot);
    this.restorers.push(() => res.setSubstitution("mailcards", null));
    // Design in alle offenen Fenster (neue übernimmt der docObserver);
    // die Version in der Adresse umgeht Thunderbirds Stylesheet-Zwischenspeicher
    ThemeSheet.uri = `resource://mailcards/theme.css?v=${extensionVersion}`;
    ThemeSheet.init();
    for (const win of Services.wm.getEnumerator(null)) {
      ThemeSheet.applyTree(win);
    }
    this.restorers.push(() => ThemeSheet.removeAll());
    if (!Services.prefs.getBoolPref("extensions.mailcards.appleIcons", true)) {
      return;
    }
    const sss = Cc["@mozilla.org/content/style-sheet-service;1"].getService(Ci.nsIStyleSheetService);
    const uri = Services.io.newURI(`resource://mailcards/icon-vars.css?v=${extensionVersion}`);
    if (!sss.sheetRegistered(uri, sss.USER_SHEET)) {
      sss.loadAndRegisterSheet(uri, sss.USER_SHEET);
    }
    this.restorers.push(() => {
      if (sss.sheetRegistered(uri, sss.USER_SHEET)) {
        sss.unregisterSheet(uri, sss.USER_SHEET);
      }
    });
  }

  // Kontextmenü der Nachrichten wie in Apple Mail: Archivieren, Löschen und
  // Spam als normale Zeilen (mit Text) nach „Als neue Nachricht bearbeiten“
  // statt einer Symbolleiste ganz oben. Antworten und Gelesen/Ungelesen gibt
  // es dort schon als eigene Einträge bzw. im Untermenü „Markieren“.
  hookMailContext(doc) {
    const popup = doc.getElementById("mailContext");
    const group = doc.getElementById("mailContext-navigation");
    if (!popup || !group || popup.__mcList) {
      return;
    }
    popup.__mcList = true;
    group.classList.add("mc-nav-list");
    const sep = doc.getElementById("mailContext-sep-navigation");
    const anchor = doc.getElementById("mailContext-editAsNew")?.nextElementSibling;
    if (anchor?.localName == "menuseparator") {
      anchor.after(group);
      if (sep) {
        group.after(sep);
      }
    }
    // Den Text (Fluent setzt dort nur aria-label) zeigt userChrome.css an.
  }

  // Heute-Leiste (Aufgaben/Termine rechts) gehört nicht in den Chat – wie in
  // Apples Nachrichten-App. Einmalig für den Chat-Bereich ausblenden; danach
  // gilt wieder, was man selbst einstellt.
  hideTodayPaneInChatOnce(w) {
    const PREF = "extensions.mailcards.todayPaneChatHidden";
    if (Services.prefs.getBoolPref(PREF, false)) {
      return;
    }
    const pane = w.document.getElementById("today-pane-panel");
    if (!pane) {
      return;
    }
    const modes = new Set((pane.getAttribute("collapsedinmodes") || "").split(",").filter(Boolean));
    modes.add("chat");
    pane.setAttribute("collapsedinmodes", [...modes].join(","));
    Services.xulStore.persist(pane, "collapsedinmodes");
    if (w.gCurrentMode == "chat") {
      w.TodayPane?.setVisible?.(false);
    }
    Services.prefs.setBoolPref(PREF, true);
  }

  // Termin-Details: an den Inhalt anpassen (mindestens 480 px breit, höchstens
  // so groß wie der Bildschirm) und iClouds Platzhalter-Erinnerung ausblenden
  // (Apple legt für Standard-Erinnerungen eine feste vom 1. April 1976 an)
  tidyEventDialog(dlg, tries = 0) {
    try {
      const frame = dlg.document.getElementById("calendar-item-panel-iframe")?.contentDocument;
      if ((!frame || frame.readyState != "complete" || !frame.querySelector("label")) && tries < 20) {
        dlg.setTimeout(() => this.tidyEventDialog(dlg, tries + 1), 250);
        return;
      }
      const strip = text => text.replace(/\s*:\s*$/, "").replace(/:\s+$/, "");
      // Fenstertitel „Neuer Termin:“ → „Neuer Termin“ (auch nach Änderungen)
      const fixTitle = () => {
        const t = dlg.document.title;
        const fixed = t.replace(/:\s*$/, "");
        if (fixed != t) {
          dlg.document.title = fixed;
        }
      };
      fixTitle();
      const titleEl = dlg.document.querySelector("title");
      if (titleEl) {
        new dlg.MutationObserver(fixTitle).observe(titleEl, { childList: true, characterData: true, subtree: true });
      }
      const idoc = dlg.document.getElementById("calendar-item-panel-iframe")?.contentDocument;
      if (!idoc) {
        return;
      }
      // Beschriftungen und Reiter ohne Doppelpunkt (Fluent setzt sie neu → beobachten)
      const fixLabels = () => {
        for (const el of idoc.querySelectorAll("label, tab")) {
          const v = el.getAttribute("value");
          if (v && /:\s*$/.test(v)) {
            el.setAttribute("value", strip(v));
          }
          const l = el.getAttribute("label");
          if (l && /:\s*$/.test(l)) {
            el.setAttribute("label", strip(l));
          }
          if (!v && !l && el.childElementCount == 0 && /:\s*$/.test(el.textContent)) {
            el.textContent = strip(el.textContent);
          }
        }
      };
      fixLabels();
      new dlg.MutationObserver(() => dlg.setTimeout(fixLabels, 0)).observe(idoc.documentElement, {
        subtree: true, attributes: true, attributeFilter: ["value", "label"], childList: true, characterData: true,
      });
    } catch (e) {
      log("event dialog tidy error", String(e).slice(0, 120));
    }
  }

  fitAlarmDialog(dlg) {
    try {
      const doc = dlg.document;
      const list = doc.getElementById("alarm-richlist");
      if (!list) {
        return;
      }
      const fit = () => {
        if (dlg.closed) {
          return;
        }
        const items = [...list.children].filter(i => i.getBoundingClientRect().height);
        if (!items.length) {
          return;
        }
        // höchstens vier Einträge ohne Scrollen, darüber scrollt die Liste
        const shown = items.slice(0, 4);
        const cs = dlg.getComputedStyle(list);
        let content = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
        for (const item of shown) {
          const ics = dlg.getComputedStyle(item);
          content += item.getBoundingClientRect().height + (parseFloat(ics.marginTop) || 0) + (parseFloat(ics.marginBottom) || 0);
        }
        const rest = dlg.innerHeight - list.getBoundingClientRect().height;
        const inner = Math.ceil(rest + content);
        if (Math.abs(inner - dlg.innerHeight) >= 2) {
          dlg.resizeTo(dlg.outerWidth, dlg.outerHeight - dlg.innerHeight + inner);
        }
      };
      fit();
      // Einträge kommen hinzu oder werden erledigt
      new dlg.MutationObserver(() => dlg.setTimeout(fit, 50)).observe(list, { childList: true });
    } catch (e) {
      log("alarm size error", String(e).slice(0, 120));
    }
  }

  fitSummaryDialog(dlg) {
    try {
      const doc = dlg.document;
      const cell = doc.querySelector(".reminder-details");
      if (cell) {
        const year = /\b1976\b/;
        for (const node of [...cell.childNodes]) {
          if (node.nodeType == 3 && year.test(node.textContent)) {
            if (node.nextSibling?.localName == "br") {
              node.nextSibling.remove();
            }
            node.remove();
          }
        }
        if (cell.lastChild?.localName == "br") {
          cell.lastChild.remove();
        }
      }
      // Titel steht groß im Inhalt – nicht zusätzlich in der Fensterleiste
      if (doc.querySelector(".item-title")?.textContent.trim()) {
        doc.title = " ";
      }
      dlg.sizeToContent();
      const maxW = dlg.screen.availWidth - 40;
      const maxH = dlg.screen.availHeight - 40;
      const width = Math.min(maxW, Math.max(480, dlg.outerWidth));
      const height = Math.min(maxH, dlg.outerHeight);
      dlg.resizeTo(width, height);
      // ein zweites Mal, falls der breitere Text weniger Zeilen braucht
      dlg.setTimeout(() => {
        dlg.sizeToContent();
        dlg.resizeTo(Math.min(maxW, Math.max(480, dlg.outerWidth)), Math.min(maxH, dlg.outerHeight));
      }, 50);
    } catch (e) {
      log("summary size error", String(e).slice(0, 120));
    }
  }

  // Feedback: neue Mail an die Feedback-Adresse, mit Versionen zum Nachvollziehen
  async sendFeedback() {
    const de = Services.locale.appLocaleAsBCP47.startsWith("de");
    let version = extensionVersion;
    try {
      const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      version = (await AddonManager.getAddonByID("mail-cards@sebastian.local"))?.version || version;
    } catch {}
    const mac = Services.sysinfo.getProperty("version");
    const subject = `halo.spaces ${version} – Feedback`;
    const body = (de ? "Hallo,\n\n\n\n—\n" : "Hi,\n\n\n\n—\n") +
      `halo.spaces ${version} · Thunderbird ${Services.appinfo.version} · macOS (Darwin ${mac})`;
    const params = Cc["@mozilla.org/messengercompose/composeparams;1"].createInstance(Ci.nsIMsgComposeParams);
    const fields = Cc["@mozilla.org/messengercompose/composefields;1"].createInstance(Ci.nsIMsgCompFields);
    fields.to = FEEDBACK_ADDRESS;
    fields.subject = subject;
    fields.body = body;
    params.type = Ci.nsIMsgCompType.New;
    params.format = Ci.nsIMsgCompFormat.PlainText;
    params.composeFields = fields;
    MailServices.compose.OpenComposeWindowWithParams(null, params);
  }

  // Update auf Wunsch: dieselbe Prüfung wie Thunderbirds tägliche, nur sofort.
  // Ergebnis: { available, version, install() } | { error } | {} (aktuell)
  async findUpdate() {
    const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
    const addon = await AddonManager.getAddonByID("mail-cards@sebastian.local");
    if (!addon) {
      return { error: true };
    }
    return new Promise(resolve => {
      let found = null;
      addon.findUpdates({
        onUpdateAvailable: (_addon, install) => {
          found = { available: true, version: install.version, install: () => install.install() };
        },
        onUpdateFinished: (_addon, error) => resolve(found || (error ? { error: true } : {})),
      }, AddonManager.UPDATE_WHEN_USER_REQUESTED);
    });
  }

  // Info-Fenster „Halo Spaces“ (Help-Menü): Version, Updates, Feedback, Spenden
  async openHaloWindow(w, { platformNote = false } = {}) {
    const open = [...Services.wm.getEnumerator(null)].find(win => win.location?.href.startsWith("resource://mailcards/about/halo.html"));
    if (open) {
      open.focus();
      return;
    }
    let version = extensionVersion;
    try {
      const { AddonManager } = ChromeUtils.importESModule("resource://gre/modules/AddonManager.sys.mjs");
      version = (await AddonManager.getAddonByID("mail-cards@sebastian.local"))?.version || version;
    } catch {}
    const api = {
      german: Services.locale.appLocaleAsBCP47.startsWith("de"),
      version,
      feedbackAddress: FEEDBACK_ADDRESS,
      checkUpdate: () => this.findUpdate(),
      mac: Services.appinfo.OS == "Darwin",
      platformNote,
      photosEnabled: () => MacPhotos.enabled(),
      // Fotos aus der Kontakte-App: einschalten und gleich abgleichen
      // (macOS fragt dabei einmal nach dem Zugriff auf die Kontakte)
      setPhotos: async on => {
        Services.prefs.setBoolPref(MAC_PHOTOS_PREF, on);
        if (!on) {
          return 0;
        }
        await MacPhotos.sync();
        return MacPhotos.byEmail.size;
      },
      sendFeedback: () => this.sendFeedback(),
      donate: () => {
        const ext = Cc["@mozilla.org/uriloader/external-protocol-service;1"].getService(Ci.nsIExternalProtocolService);
        ext.loadURI(Services.io.newURI(DONATE_URL));
      },
    };
    const hw = w.openDialog("resource://mailcards/about/halo.html", "halo-spaces",
      `chrome,dialog=yes,centerscreen,resizable=no,width=360,height=${(api.mac ? 340 : 292) + (platformNote ? 64 : 0)}`);
    // erst lädt das Fenster about:blank, dann unsere Seite – darauf warten
    let tries = 0;
    const wire = () => {
      if (hw.closed || tries++ > 100) {
        return;
      }
      const doc = hw.document;
      if (doc?.documentURI?.startsWith("resource://mailcards/about/halo.html") && doc.readyState == "complete" && doc.getElementById("version")) {
        this.wireHaloWindow(hw, api);
      } else {
        w.setTimeout(wire, 30);
      }
    };
    w.setTimeout(wire, 30);
  }

  // Texte setzen und Knöpfe verbinden (aus der Erweiterung heraus)
  wireHaloWindow(hw, api) {
    const doc = hw.document;
    const de = api.german;
    const t = (deText, enText) => (de ? deText : enText);
    const $ = id => doc.getElementById(id);
    doc.documentElement.lang = de ? "de" : "en";
    for (const el of doc.querySelectorAll("[data-de]")) {
      el.textContent = de ? el.dataset.de : el.dataset.en;
    }
    $("version").textContent = `Version ${api.version}`;
    // Windows/Linux: einmaliger Hinweis beim ersten Start
    const note = $("platform-note");
    if (note && api.platformNote) {
      note.textContent = t(
        "halo.spaces ist für macOS gemacht – unter Windows und Linux wird es gerade erst erprobt. Wenn etwas komisch aussieht, freuen wir uns über eine kurze Rückmeldung!",
        "halo.spaces is made for macOS – on Windows and Linux it is still being tested. If something looks odd, we'd love a quick note!"
      );
      note.hidden = false;
    }
    $("mail").textContent = api.feedbackAddress;

    const button = $("update");
    const label = button.querySelector(".label");
    const status = $("update-status");
    let install = null;
    button.addEventListener("click", async () => {
      if (install) {
        button.disabled = true;
        label.textContent = t("Wird installiert …", "Installing …");
        try {
          await install();
          label.textContent = t("Installiert – wird gleich aktiv", "Installed – active in a moment");
        } catch {
          label.textContent = t("Installation fehlgeschlagen", "Installation failed");
          button.disabled = false;
        }
        button.classList.remove("available");
        install = null;
        return;
      }
      button.disabled = true;
      label.textContent = t("Suche nach Updates …", "Checking for updates …");
      status.textContent = "";
      const result = await api.checkUpdate();
      button.disabled = false;
      if (result.available) {
        install = result.install;
        button.classList.add("available");
        label.textContent = t(`Version ${result.version} installieren`, `Install version ${result.version}`);
      } else if (result.error) {
        label.textContent = t("Keine Verbindung – erneut versuchen", "No connection – try again");
      } else {
        label.textContent = t("halo.spaces ist aktuell", "halo.spaces is up to date");
        status.textContent = "✓";
      }
    });
    const feedback = event => {
      event.preventDefault();
      api.sendFeedback();
      hw.close();
    };
    // Mac: Absenderbilder aus der Kontakte-App
    const photos = $("photos");
    if (api.mac && photos) {
      const pLabel = photos.querySelector(".label");
      const pStatus = $("photos-status");
      const show = on => {
        pLabel.textContent = on
          ? t("Fotos aus Kontakte: an", "Photos from Contacts: on")
          : t("Fotos aus Kontakte verwenden", "Use photos from Contacts");
        pStatus.textContent = on ? "✓" : "";
        photos.dataset.on = on ? "1" : "";
      };
      photos.hidden = false;
      api.photosEnabled().then(show);
      photos.addEventListener("click", async () => {
        const on = !photos.dataset.on;
        photos.disabled = true;
        if (on) {
          pLabel.textContent = t("Kontakte werden gelesen …", "Reading contacts …");
          pStatus.textContent = "";
        }
        try {
          const count = await api.setPhotos(on);
          show(on);
          if (on) {
            pStatus.textContent = count
              ? `✓ ${count}`
              : t("keine – Zugriff in den Systemeinstellungen erlauben", "none – allow access in System Settings");
          }
        } catch {
          show(false);
        }
        photos.disabled = false;
      });
    }
    $("feedback").addEventListener("click", feedback);
    $("mail").addEventListener("click", feedback);
    $("donate").addEventListener("click", () => api.donate());
    // Logo mit Versionsnummer laden (sonst zeigt Thunderbird nach einem
    // Update noch das zwischengespeicherte alte)
    const icon = doc.querySelector(".icon");
    if (icon) {
      icon.src = `icon.svg?v=${api.version}`;
    }
  }

  stop() {
    ExtensionSupport.unregisterWindowListener("mail-cards");
    this.mainWindows.clear();
    for (const restore of this.restorers.splice(0)) {
      try {
        restore();
      } catch {}
    }
    this.windows.clear();
  }

  anyWindow() {
    for (const w of this.windows) {
      if (!w.closed) {
        return w;
      }
      this.windows.delete(w);
    }
    return null;
  }

  patch(win, attempt) {
    if (this.windows.has(win) || win.closed) {
      return;
    }
    const Card = win.customElements?.get("thread-card");
    if (!Card || !win.threadPane || !win.threadTree) {
      if (attempt < 100) {
        win.setTimeout(() => this.patch(win, attempt + 1), 200);
      } else {
        log("patch gave up", { card: !!Card, threadPane: !!win.threadPane, threadTree: !!win.threadTree });
      }
      return;
    }
    this.windows.add(win);
    const doc = win.document;
    this.hookMailContext(doc);
    colorAccountRows(doc);
    const mb = win.messageBrowser?.contentDocument;
    if (mb?.readyState == "complete") {
      this.hookMailContext(mb);
    }
    const threadPane = win.threadPane;

    // Die echten Thunderbird-Funktionen am Fenster merken. So überschreibt
    // eine neue Version beim Aktualisieren nie die Hülle der alten, und die
    // alte stellt beim Beenden nichts zurück, was ihr nicht mehr gehört.
    const reg = (win.__mailCards ??= {
      fill: Card.prototype.fillRow,
      density: threadPane.densityChange,
      owner: null,
    });
    const TableRow = win.customElements.get("thread-row");
    reg.rowFill ??= TableRow?.prototype.fillRow;
    const token = (this.token ??= Symbol("mail-cards"));
    reg.owner = token;

    doc.getElementById(STYLE_ID)?.remove();
    const style = doc.createElement("style");
    style.id = STYLE_ID;
    style.textContent =
      CSS +
      `#threadTree tr[is="thread-card"] .mc-preview { -webkit-line-clamp: ${this.previewLines}; }`;
    doc.head.appendChild(style);

    const enhancer = this;
    let decorateErrors = 0;
    const fill = function () {
      reg.fill.call(this);
      try {
        enhancer.decorate(win, this);
      } catch (e) {
        if (decorateErrors++ < 5) {
          log("decorate error", e);
        }
      }
    };
    Card.prototype.fillRow = fill;

    const extra = this.previewLines ? this.previewLines * 16 + 10 : 0;
    const density = async function (...args) {
      await reg.density.apply(this, args);
      Card.ROW_HEIGHT = Math.max(Card.ROW_HEIGHT + extra, 52);
      this.mcCardHeight = Card.ROW_HEIGHT; // Kontaktkarten im Adressbuch gleich hoch
      // Tabellenansicht: 14-px-Schrift (userChrome.css) braucht luftigere Zeilen
      const Row = win.customElements.get("thread-row");
      if (Row) {
        Row.ROW_HEIGHT = Math.max(Row.ROW_HEIGHT, 28);
      }
    };
    threadPane.densityChange = density;

    // Tabellenansicht: jede zweite Zeile leicht getönt (data-mc-odd nach der
    // echten Listenposition – die Zeilen werden beim Scrollen wiederverwendet)
    if (TableRow && reg.rowFill) {
      TableRow.prototype.fillRow = function (...args) {
        const result = reg.rowFill.apply(this, args);
        // als Attribut – Thunderbird setzt die Klassen der Zeile neu
        this.toggleAttribute("data-mc-odd", this._index % 2 == 1);
        return result;
      };
    }

    this.restorers.push(() => {
      if (reg.owner !== token) {
        return; // eine neuere Version hat übernommen
      }
      Card.prototype.fillRow = reg.fill;
      if (TableRow && reg.rowFill) {
        TableRow.prototype.fillRow = reg.rowFill;
      }
      threadPane.densityChange = reg.density;
      delete win.__mailCards;
      style.remove();
      for (const el of doc.querySelectorAll(".mc-avatar, .mc-preview")) {
        el.remove();
      }
      threadPane.updateThreadItemSize();
    });

    this.trackToolbarOffset(win);
    this.decorateFolders(win);
    this.hookFolderEvents(win);

    win.addEventListener("unload", () => this.windows.delete(win), {
      once: true,
    });
    threadPane.updateThreadItemSize();
    log("patched about:3pane", { attempt, rows: win.threadTree?.view?.rowCount ?? null, folder: win.gFolder?.URI || null });
  }

  // Kopfzeile über der Mailliste aktuell halten: bei Ordnerwechsel und wenn
  // sich die Anzahl ändert (auch wenn Thunderbirds eigene Kopfzeile aus ist)
  hookFolderEvents(win) {
    const top = win.browsingContext?.topChromeWindow;
    const tph = win.threadPaneHeader;
    if (!top || !tph || tph.__mcHooked) {
      return;
    }
    const self = this;
    const update = () => win.setTimeout(() => self.updateListHeader(top), 0);
    const origSelected = tph.onFolderSelected;
    const origCount = tph.updateMessageCount;
    tph.onFolderSelected = function (...args) {
      update();
      return origSelected.apply(this, args);
    };
    tph.updateMessageCount = function (...args) {
      update();
      return origCount.apply(this, args);
    };
    tph.__mcHooked = true;
    win.addEventListener("folderURIChanged", update);
    this.restorers.push(() => {
      tph.onFolderSelected = origSelected;
      tph.updateMessageCount = origCount;
      delete tph.__mcHooked;
      win.removeEventListener("folderURIChanged", update);
    });
    update();
  }

  // Ordnerliste wie Apple Mail: oben „Favourites“ mit All Inboxes und All
  // Sent, darunter „On My Mac“ und je Konto alle Ordner – mit einheitlichen
  // Namen, Apple-Reihenfolge und ohne Gmails Zwischenebene „[Gmail]“.
  // Einmalig wie Apple Mail: „Sammelordner“ (Alle Eingänge, Alle
  // gesendeten …) oben in der Ordnerliste einschalten. Wer sie danach wieder
  // abschaltet, behält das so.
  enableUnifiedOnce(win, tries = 0) {
    const PREF = "extensions.mailcards.unifiedApplied";
    if (Services.prefs.getBoolPref(PREF, false)) {
      return;
    }
    const pane = win.folderPane;
    if (!pane?.isInitialized) {
      if (tries < 40 && !win.closed) {
        win.setTimeout(() => this.enableUnifiedOnce(win, tries + 1), 500);
      }
      return;
    }
    try {
      const modes = pane.activeModes;
      if (!modes.includes("smart")) {
        pane.activeModes = ["smart", ...modes];
      }
      Services.prefs.setBoolPref(PREF, true);
    } catch (e) {
      log("unified folders error", e);
    }
  }

  decorateFolders(win) {
    const doc = win.document;
    const tree = doc.getElementById("folderTree");
    if (!tree) {
      return;
    }
    this.enableUnifiedOnce(win);
    const L = appleLabels();
    const ORDER = FOLDER_ORDER;
    const roleOf = folderRole;
    const setText = (el, text) => {
      if (el && text && !L.native && el.textContent != text) {
        el.textContent = text;
      }
    };
    const setAttr = (el, name, on) => {
      if (on && !el.hasAttribute(name)) {
        el.setAttribute(name, "");
      } else if (!on && el.hasAttribute(name)) {
        el.removeAttribute(name);
      }
    };

    // Lokale Ordner nur zusammenklappen, wenn darin nichts Eigenes liegt
    // (nur leere Standardordner) – POP3-Konten mit globalem Posteingang,
    // Archive oder Filterziele dort bleiben sichtbar
    const localIsEmpty = () => {
      try {
        const root = MailServices.accounts.localFoldersServer?.rootFolder;
        return !root || root.subFolders.every(f => !f.hasSubFolders && f.getTotalMessages(false) == 0);
      } catch {
        return false;
      }
    };
    const apply = () => {
      // Favoriten nur straffen, wenn darunter auch „Alle Ordner“ angezeigt
      // wird – sonst wären die übrigen Ordner gar nicht erreichbar
      const allShown = !!tree.querySelector(':scope > li[data-mode="all"]');
      if (!L.native) {
        for (const header of tree.querySelectorAll(':scope > li[data-mode="smart"] > .mode-container .mode-name')) {
          header.removeAttribute("data-l10n-id");
          setText(header, L.favourites);
        }
      }
      const hideLocal = localIsEmpty();
      for (const li of tree.querySelectorAll('li[is="folder-tree-row"]')) {
        const modeLi = li.closest("li[data-mode]");
        const mode = modeLi?.dataset.mode;
        let folder = null;
        try {
          folder = MailServices.folderLookup.getFolderForURL(li.uri);
        } catch {}
        const label = li.querySelector(":scope > .container .name");
        const topLevel = li.parentElement?.parentElement === modeLi;

        if (mode == "smart") {
          if (li.hasAttribute("data-server-type")) {
            setAttr(li, "data-mc-hide", allShown); // Konto-Abschnitte gibt es unten schon
            continue;
          }
          if (topLevel) {
            const type = li.dataset.folderType;
            setAttr(li, "data-mc-hide", allShown && type != "inbox" && type != "sent");
            if (type == "inbox") setText(label, L.allInboxes);
            if (type == "sent") setText(label, L.allSent);
          } else if (folder?.server) {
            setText(label, folder.server.prettyName); // „Google“, „iCloud“
          }
          continue;
        }

        if (mode != "all") {
          continue;
        }
        if (li.hasAttribute("data-server-type")) {
          if (li.dataset.serverType == "none") {
            setText(label, L.onMyMac);
            li.querySelectorAll(':scope > ul > li').forEach(c => setAttr(c, "data-mc-hide", hideLocal));
          }
          continue;
        }
        // Gmails Zwischenordner „[Gmail]“ auflösen
        const isGmailContainer = folder && !roleOf(folder) && folder.parent?.isServer &&
          /^\[(Gmail|Google Mail)\]$/.test(folder.name);
        setAttr(li, "data-mc-flatten", isGmailContainer);
        if (isGmailContainer) {
          li.querySelector(":scope > ul")?.style.setProperty("--depth", "1");
          continue;
        }
        // Gmail wie Apple Mail: „Markiert“ (Starred) und „Notes“ ausblenden,
        // „Wichtig“ (Important) an den Anfang
        // Gmail an der Ordneradresse erkennen (server.hostName ist hier leer)
        const gmail = /^imap:\/\/[^/]*@?imap\.(gmail|googlemail)\.com\//i.test(li.uri || "");
        const directChild = folder?.parent && (folder.parent.isServer || /^\[(Gmail|Google Mail)\]$/.test(folder.parent.name));
        if (gmail && directChild && !roleOf(folder)) {
          if (/^(Markiert|Mit Stern|Starred|Notes|Notizen)$/i.test(folder.name)) {
            setAttr(li, "data-mc-hide", true);
            continue;
          }
          if (/^(Wichtig|Important)$/i.test(folder.name)) {
            li.style.order = "0";
            continue;
          }
        }
        const role = roleOf(folder);
        if (role && folder.parent && (folder.parent.isServer || /^\[(Gmail|Google Mail)\]$/.test(folder.parent.name))) {
          setText(label, L[role]);
          li.style.order = String(ORDER[role]);
        } else if (topLevel === false && (folder?.parent?.isServer || /^\[(Gmail|Google Mail)\]$/.test(folder?.parent?.name || ""))) {
          li.style.order = "10"; // eigene Ordner nach den Standardordnern
        }
      }
    };

    let pending = false;
    const observer = new win.MutationObserver(() => {
      if (pending) {
        return;
      }
      pending = true;
      win.requestAnimationFrame(() => {
        pending = false;
        observer.disconnect();
        try {
          apply();
        } catch (e) {
          log("decorateFolders error", e);
        }
        observer.observe(tree, { childList: true, subtree: true, characterData: true });
      });
    });
    try {
      apply();
    } catch (e) {
      log("decorateFolders error", e);
    }
    observer.observe(tree, { childList: true, subtree: true, characterData: true });
    this.restorers.push(() => {
      observer.disconnect();
      for (const li of tree.querySelectorAll("[data-mc-hide], [data-mc-flatten]")) {
        li.removeAttribute("data-mc-hide");
        li.removeAttribute("data-mc-flatten");
      }
      win.folderPane?.activeModes && (win.folderPane.activeModes = win.folderPane.activeModes); // Namen neu aufbauen
    });
  }

  decorate(win, row) {
    const doc = win.document;
    const container = row.querySelector(".card-container");
    if (!container) {
      return;
    }
    let avatar = container.querySelector(":scope > .mc-avatar");
    if (!avatar) {
      avatar = doc.createElement("div");
      avatar.className = "mc-avatar";
      container.insertBefore(avatar, container.children[1] || null);
    }
    let preview = row.querySelector(".mc-preview");
    if (!preview && this.previewLines) {
      preview = doc.createElement("div");
      preview.className = "mc-preview";
      row.querySelector(".thread-card-dynamic-row")?.after(preview);
    }

    if ((row.dataset.properties || "").split(" ").includes("dummy")) {
      return;
    }

    const hdr = this.hdrForRow(row);
    if (!hdr) {
      return;
    }

    if (preview) {
      const text = cleanPreview(hdr.getStringProperty("preview"));
      preview.textContent = text;
      if (!text) {
        this.requestPreview(win, hdr);
      }
    }

    this.fillAvatar(avatar, hdr);
  }

  // Wie Apple Mail: Eine zugeklappte Konversation zeigt Vorschau und Bild der
  // neuesten Nachricht, nicht der ersten. Aufgeklappt hat jede Zeile ihre eigene.
  hdrForRow(row) {
    let hdr;
    try {
      hdr = row.view.getMsgHdrAt(row._index);
    } catch {
      return null;
    }
    if (!hdr || !row.classList.contains("children") || !row.classList.contains("collapsed")) {
      return hdr;
    }
    try {
      const thread = row.view.getThreadContainingIndex(row._index);
      let latest = hdr;
      for (let i = 0; i < thread.numChildren; i++) {
        const child = thread.getChildHdrAt(i);
        if (child && child.date > latest.date) {
          latest = child;
        }
      }
      return latest;
    } catch {
      return hdr;
    }
  }

  fillAvatar(avatar, hdr) {
    let name = "";
    let email = "";
    try {
      const parsed = MailServices.headerParser.parseDecodedHeader(
        hdr.mime2DecodedAuthor || hdr.author
      )[0];
      name = parsed?.name || "";
      email = (parsed?.email || "").toLowerCase();
    } catch {}

    avatar.dataset.email = email;
    const initials = initialsFor(name, email);
    const show = result => {
      if (avatar.dataset.email != email) {
        return; // Zeile wurde inzwischen für eine andere Nachricht verwendet
      }
      if (result?.src) {
        let img = avatar.querySelector("img");
        if (!img) {
          avatar.textContent = "";
          img = avatar.ownerDocument.createElement("img");
          img.alt = "";
          avatar.appendChild(img);
        }
        if (img.getAttribute("src") != result.src) {
          img.setAttribute("src", result.src);
        }
        avatar.classList.add("mc-has-img");
        avatar.classList.toggle("mc-small", !!result.small);
      } else {
        avatar.classList.remove("mc-has-img", "mc-small");
        avatar.textContent = initials;
      }
    };

    if (!email) {
      show(null);
      return;
    }
    const known = this.avatars.peek(email);
    if (known !== undefined) {
      show(known);
      return;
    }
    show(null);
    // in Werbung/Junk keine Logos laden (das würde Spam-Absendern zeigen,
    // dass die Mail angesehen wurde)
    try {
      if (hdr.folder?.getFlag(Ci.nsMsgFolderFlags.Junk) || hdr.getStringProperty("junkscore") == "100") {
        return;
      }
    } catch {}
    this.avatars.resolve(email).then(show);
  }

  requestPreview(win, hdr) {
    const folder = hdr.folder;
    if (!folder) {
      return;
    }
    const id = `${folder.URI}#${hdr.messageKey}`;
    if (this.requested.has(id)) {
      return;
    }
    this.requested.add(id);
    if (!this.pendingPreview.has(folder)) {
      this.pendingPreview.set(folder, []);
    }
    this.pendingPreview.get(folder).push(hdr);
    this.stats.quick++;
    if (!this.previewTimer) {
      this.previewTimer = win.setTimeout(() => this.flushPreviews(), 150);
    }
  }

  flushPreviews() {
    this.previewTimer = null;
    const batches = [...this.pendingPreview];
    this.pendingPreview.clear();
    for (const [folder, hdrs] of batches) {
      // Schritt 2: was danach noch leer ist (z. B. HTML-Mails, deren erste
      // 2 KB nur aus <head>/<style> bestehen), aus der ganzen Nachricht holen.
      const afterQuick = () => {
        this.refreshPreviews();
        for (const hdr of hdrs) {
          if (!cleanPreview(hdr.getStringProperty("preview"))) {
            this.fullQueue.push(hdr);
          }
        }
        this.pumpFull();
      };
      const listener = {
        QueryInterface: ChromeUtils.generateQI(["nsIUrlListener"]),
        OnStartRunningUrl() {},
        OnStopRunningUrl: () => afterQuick(),
      };
      try {
        // Schritt 1: Thunderbirds eigene, schnelle Vorschau (Anfang der Mail)
        const async = folder.fetchMsgPreviewText(
          hdrs.map(h => h.messageKey),
          listener
        );
        if (!async) {
          afterQuick();
        }
      } catch (e) {
        log("quick preview error", e);
        afterQuick();
      }
    }
  }

  pumpFull() {
    while (this.fullActive < 2 && this.fullQueue.length) {
      const hdr = this.fullQueue.shift();
      if (cleanPreview(hdr.getStringProperty("preview"))) {
        continue;
      }
      this.fullActive++;
      let done = false;
      const finish = () => {
        if (done) {
          return;
        }
        done = true;
        this.fullActive--;
        this.refreshPreviews();
        this.pumpFull();
      };
      setTimeout(finish, 20000);
      try {
        MsgHdrToMimeMessage(
          hdr,
          null,
          (msgHdr, mime) => {
            try {
              const text = mime
                ? cleanPreview(mime.coerceBodyToPlaintext(msgHdr.folder))
                : "";
              if (text) {
                // dauerhaft speichern – Thunderbird nutzt dieselbe Eigenschaft
                msgHdr.setStringProperty("preview", text);
              }
              this.stats.full[text ? "ok" : mime ? "empty" : "nomime"]++;
            } catch (e) {
              log("preview parse error", e);
            }
            finish();
          },
          // nur aus der lokalen Kopie lesen – sonst würde für jede Vorschau
          // die ganze Mail vom Server geladen (IMAP ohne Offline-Kopie, Exchange)
          (() => {
            try {
              const folder = hdr.folder;
              return folder.server.type == "none" || folder.server.type == "pop3" || folder.server.type == "rss" ||
                folder.getFlag(Ci.nsMsgFolderFlags.Offline);
            } catch {
              return false;
            }
          })(),
          { saneBodySize: true, examineEncryptedParts: false }
        );
      } catch (e) {
        this.stats.full.error++;
        if (this.stats.full.error < 5) {
          log("full fetch error", e);
        }
        finish();
      }
    }
    if (!this.fullActive && !this.fullQueue.length && !this.statsLogged) {
      this.statsLogged = true;
      setTimeout(() => {
        log("preview stats", this.stats);
        this.statsLogged = false;
      }, 3000);
    }
  }

  refreshPreviews() {
    for (const win of this.windows) {
      if (win.closed) {
        continue;
      }
      for (const row of win.document.querySelectorAll(
        '#threadTree tr[is="thread-card"]'
      )) {
        const preview = row.querySelector(".mc-preview");
        if (!preview || preview.textContent) {
          continue;
        }
        try {
          const hdr = this.hdrForRow(row);
          preview.textContent = cleanPreview(hdr?.getStringProperty("preview"));
        } catch {}
      }
    }
  }
}

// ---------------------------------------------------------------------------
// WebExtension-Experiment
// ---------------------------------------------------------------------------

var enhancer = null;
var extensionRoot = null; // rootURI der Erweiterung, für resource://mailcards/
var extensionVersion = ""; // hängt an den Stylesheet-Adressen, damit ein Update sofort greift

this.mailCards = class extends ExtensionCommon.ExtensionAPI {
  getAPI(context) {
    return {
      mailCards: {
        async start(options) {
          extensionRoot ||= context.extension.rootURI;
          extensionVersion ||= context.extension.version;
          if (enhancer) {
            return;
          }
          log("start", options || {}, Services.appinfo.version);
          enhancer = new CardEnhancer(options || {});
          enhancer.start();
        },
      },
    };
  }

  // Start direkt beim Programmstart („events: startup“ im Manifest) – ohne
  // Umweg über die Hintergrundseite. Thunderbird kann nach Updates eine
  // veraltete Hintergrundseite aus dem Zwischenspeicher laden; dann würde
  // background.js nie laufen. Die Hintergrundseite ist nur noch Reserve.
  onStartup() {
    if (enhancer) {
      return;
    }
    extensionRoot = this.extension.rootURI;
    extensionVersion = this.extension.version;
    log("start (onStartup)", { version: this.extension.version }, Services.appinfo.version);
    enhancer = new CardEnhancer({});
    enhancer.start();
  }

  onShutdown(isAppShutdown) {
    if (isAppShutdown) {
      return;
    }
    enhancer?.stop();
    enhancer = null;
  }
};
