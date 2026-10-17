# halo.spaces

<p align="center">
  <img src="extension/about/icon.svg" alt="halo.spaces logo" width="128">
</p>

halo.spaces gives Mozilla Thunderbird on macOS a calm, tidy look inspired by
Apple Mail, Calendar and Contacts. It adds coloured spaces on the left and
uses the same layout in every space.

It is one package for Thunderbird 128+: the theme, its own Apple-style icons,
and an extension for the things CSS alone can't do.

Released under the Mozilla Public License 2.0

<p align="center">
  <img src="screenshots/mail.png" alt="halo.spaces – mail with Today pane" width="90%">
</p>

---------------------------------------------------------------

Features
--------
- **Apple Mail layout**: card list with a two-line preview, sender logos (address book, macOS Contacts, BIMI, website icon, otherwise initials), unified inboxes and the search field top right
- **Coloured spaces**: Mail, Contacts, Calendar, Tasks and Chat, all with the same toolbar and sidebar edges. Sidebars slide in and out, and a double-click on a divider resets it
- **Calendar like Apple Calendar**: Day, Week, Multiweek and Month switcher in the title bar, a month view without scrollbars, and a **quick event/task window** for new entries
- **Today pane**: runs to the top of the window, has a mini calendar plus an agenda card to the end of the month, and marks upcoming events with "now" or "in 2 hr"
- **Unified address book**: duplicates merged, account labels in the account colours
- **Light and dark** follow the system, and the accent colour follows macOS
- No scrollbars anywhere. Scrolling still works with the wheel, trackpad and keyboard
- Automatic updates via GitHub

<p align="center">
  <img src="screenshots/calendar.png" alt="Calendar month view" width="49%">
  <img src="screenshots/addressbook.png" alt="Address book" width="49%">
</p>

<p align="center">
  <img src="screenshots/quick-event.png" alt="Quick event window" width="320">
</p>

Personal data in the screenshots is blurred.

3.0.95 Release Notes
--------
- Quick event window: type naturally, e.g. "tomorrow 12:30 for 90 min". A double-click in the calendar opens it too
- Mail cards: flag, archive and delete on hover
- Birthdays from your address books as their own calendar
- A settings page (Add-ons and Themes → halo.spaces → Preferences)
- Visible keyboard focus on halo.spaces controls

See [Releases](https://github.com/sruf79/halo-spaces/releases) for all versions.

Credits
--------
halo.spaces uses the coffee cup from [Noto Emoji](https://github.com/googlefonts/noto-emoji)
(© Google LLC, Apache License 2.0) – see `extension/about/NOTICE.txt`.
The layout of this page follows [FluentBird](https://github.com/Deathbyteacup/fluentbird) by Danny King.

---------------------------------------------------------------

Setup Instructions
------------------

1. Download the latest `halo-spaces-<version>.xpi` from
   [Releases](https://github.com/sruf79/halo-spaces/releases).

2. In Thunderbird open **Add-ons and Themes** → gear icon →
   **Install Add-on From File…** and choose the file.

3. Under **Themes**, select **System theme – auto**.
   *Do not* select Light, Dark or a theme from the add-on store.

4. Restart Thunderbird once.

Updates arrive automatically (Thunderbird checks every 24 hours). To check
right away: **Help → halo.spaces… → Check for Updates**.

No `userChrome.css` is needed. The theme ships inside the extension. An older
copy of this theme in your profile's `chrome` folder takes precedence and
would hide updates, so remove it.

---------------------------------------------------------------

Known Issues
------------
- Made for **macOS**. Windows and Linux work, but they aren't the focus.
  Window buttons and some spacing differ there, and you'll see a short note
  on first start.
- The compose window and a few dialogs are only partly themed.
- Report issues via [GitHub Issues](https://github.com/sruf79/halo-spaces/issues). Please include your OS, Thunderbird version and a screenshot.

Settings for turning parts off (Config Editor):

| Preference | Effect |
|---|---|
| `extensions.mailcards.bundledTheme = false` | turns off the bundled theme |
| `extensions.mailcards.appleIcons = false` | keeps Thunderbird's own icons |
| `extensions.mailcards.calendarOffline = true` | turns on offline support for online calendars (faster loading) |

---------------------------------------------------------------

Development
-----------

| Folder/File | Content |
|---|---|
| `chrome/userChrome.css` | theme (mail, menus, dialogs) |
| `chrome/spaces.css` | calendar, tasks, contacts, chat, settings – merged in by `chrome/merge_spaces.py` |
| `icons/` | toolbar, folder and `--icon-*` replacement icons |
| `extension/` | the extension (manifest, `api/implementation.js`) |

```bash
./build.sh                       # → dist/halo-spaces-<version>.xpi (includes theme.css)
python3 tests/halo_test.py       # automated checks in a fresh, temporary profile
./release.sh 3.1.0               # version, update URL, runs the tests, writes updates.json
./publish.sh 3.1.0 notes.md      # uploads exactly that package and verifies the hash
```

---------------------------------------------------------------

Questions or feedback?
In Thunderbird: **Help → halo.spaces… → Send Feedback**, or open an issue here. Enjoy!
