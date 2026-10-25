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
    { key: "senderLogos", label: t("Logos from sender websites"),
      hint: t("asks only the sender’s own website (favicon, BIMI) – off: no outside requests") },
    { key: "macContactPhotos", mac: true, label: t("Photos from the Contacts app"),
      hint: t("macOS asks for access once") },
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
    { key: "calendarOffline", label: t("Offline copy for online calendars"),
      hint: t("faster loading; re-creates the calendars once") },
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
