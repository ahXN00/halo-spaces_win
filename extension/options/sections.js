// Optionen von halo.spaces – gemeinsam für die Einstellungsseite (options.js)
// und die Suche in Thunderbirds Einstellungen (implementation.js lädt diese
// Datei über resource://mailcards/options/sections.js). t: Übersetzung
"use strict";

// Nur was sich nicht direkt in der Oberfläche einstellen lässt (wie Apple Mail):
// Breite der Mailliste (Trennlinie ziehen, Doppelklick), doppelte Kontakte
// (Adressbuch → Ansicht), Vorschauzeilen (Mail → Ansicht) und Geburtstage
// (Häkchen am Kalender „Geburtstage“ in der Kalenderliste) stehen hier
// bewusst nicht; ihre Prefs bleiben
var SECTIONS = t => [
  [t("Mail"), [
    { key: "fullConversation", label: t("Show whole conversation"),
      hint: t("received and sent messages from all folders, newest first") },
    { key: "unreadTint", label: t("Tint unread messages"),
      hint: t("light accent colour behind unread messages, besides the dot") },
    { key: "undoSend", type: "select", options: [0, 10, 20, 30], labels: { 0: t("Off") }, unit: t("seconds"),
      label: t("Undo Send"), hint: t("like Apple Mail: the message waits this long and can still be taken back") },
    { key: "senderLogos", label: t("Logos from sender websites"),
      hint: t("asks only the sender’s own website (favicon, BIMI) – off: no outside requests") },
    { key: "macContactPhotos", mac: true, label: t("Photos from the Contacts app"),
      hint: t("macOS asks for access once") },
    { key: "darkMessages", needs: "darkReader", label: t("Dark backgrounds for messages"),
      hint: t("in dark mode, like Apple Mail – Thunderbird recolours HTML messages carefully, images stay as they are") },
    { key: "plainTextSystemFont", label: t("Messages in system font"),
      hint: t("like Apple Mail; messages with their own font keep it – off: Thunderbird’s fonts") },
    { key: "hideCollectedAddresses", label: t("Hide “Collected Addresses”"),
      hint: t("in the address book sidebar, like Apple Contacts – completion while writing keeps working") },
  ]],
  [t("Calendar"), [
    { key: "calendarEmoji", label: t("Emojis before event titles"),
      hint: t("🎂 birthday, 🏋️ training, 🦷 dentist …") },
    { key: "emojiCustom", type: "textarea", label: t("Own keywords"),
      hint: t("one per line, “keyword = emoji”, e.g. “Book club = 📖” – take precedence"),
      placeholder: t("Book club = 📖\nChoir = 🎶") },
    { key: "weather", label: t("Weather in the Today Pane"),
      hint: t("the symbol next to the title shows the current weather – asks open-meteo.com about every 30 minutes; off: the sun stays, no outside requests") + " · " + t("Weather data: Open-Meteo.com, CC BY 4.0") },
    { key: "weatherPlace", type: "place", label: t("Place for the weather"),
      hint: t("a city – empty: your current location (the system asks for permission once)"), placeholder: t("Current location") },
    { key: "calendarOffline", label: t("Offline copy for online calendars"),
      hint: t("faster loading; re-creates the calendars once") },
  ]],
  // fünfter Platz der Bereichsleiste: nur eines – Chat, Erweiterung, Webseite oder keiner
  [t("Spaces"), [
    { key: "fifthSpace", type: "select", options: ["chat", "addon", "web", "none"],
      labels: { chat: t("Chat"), addon: t("Space of an add-on"), web: t("Website"), none: t("None") },
      label: t("Fifth space"), hint: t("the place of Chat in the spaces bar – only one of them, never both") },
    { key: "fifthSpaceAddon", type: "select", choices: "fifthSpaceAddons", showIf: ["fifthSpace", "addon"],
      label: t("Add-on"), hint: t("add-ons that bring their own space; it opens unchanged in its own tab") },
    { key: "fifthSpaceUrl", type: "url", showIf: ["fifthSpace", "web"], label: t("Address"),
      hint: t("opens like an app: no address bar, links to other sites open in your browser"), placeholder: "https://…" },
    { key: "fifthSpaceIcon", type: "select", options: ["mask", "original"], showIf: ["fifthSpace", "addon", "web"],
      labels: { mask: t("In the space colour"), original: t("Original") },
      label: t("Symbol"), hint: t("original: unchanged on a white surface") },
  ]],
  [t("Appearance"), [
    { key: "inlinePrompts", label: t("Dialogs inside the window"),
      hint: t("questions appear as a sheet at the top of the window, dialogs without title bar; for newly opened windows") },
    { key: "earlyTheme", label: t("Design without flicker at start"),
      hint: t("writes a userChrome.css into your profile; from the next start") },
  ]],
  [t("Updates"), [
    { key: "autoUpdate", label: t("Install updates at start"), hint: t("checks at most every 6 hours; active after a restart") },
  ]],
  // Fehlerbehebung: nur abschalten, wenn etwas nicht stimmt
  [t("Troubleshooting"), [
    { key: "bundledTheme", label: t("halo.spaces design"), hint: t("takes effect after a restart") },
    { key: "appleIcons", label: t("Own icons"), hint: t("takes effect after a restart") },
    { key: "debug", label: t("Detailed log"),
      hint: t("mail-cards-debug.log in the profile, includes sender addresses") },
  ]],
];
