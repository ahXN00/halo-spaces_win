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
- **Coloured spaces**: Mail, Contacts, Calendar, Tasks and Chat, all with the same toolbar and sidebar edges. Sidebars slide in and out; dragging a divider all the way closes the sidebar, a double-click resets its width
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

3.6.0 Release Notes
--------
- **Hover actions like Apple Mail**: moving the pointer over an open message shows a small capsule on the line below the header – Delete | Reply, Reply All, Forward. Always on; the capsule in the message list cards is gone
- **Star button**: the flag button in the toolbar is now a split star button like Apple Mail – click the star to star or unstar the message, the arrow opens the menu as before. The Move button shows folder and arrow without a divider
- **Unread filter**: the filter button above the message list now shows only unread mail, the next click shows all again; Thunderbird's Quick Filter bar is gone
- **Faster search**: hits from Thunderbird's index (Gloda) appear right away, matches in subject, sender and recipients follow at once, the message text is searched in the background and only adds new hits – no duplicate rows, the list stays where you scrolled
- **View menu**: preview lines (none to 4) are now under View, like Apple Mail; the "…" menu above the message list gets "Show Contact Photo". "Table View: Wide" is gone – it broke the layout; whoever used it lands in the classic table
- **Sending** shows no progress window any more – progress appears in the status bar, errors still show up
- **Sidebars**: one divider for every space and the Today pane – drag it wider (up to 360 px, like the calendar; Mail can be widened again), drag it under the threshold to hide the sidebar and back in the same motion to show it again, or pull a hidden sidebar back out from the window edge. No animation
- **Contacts like Apple Contacts**: the personal address book is called "Contacts", is hidden while it is empty (show it from the "…" menu) and the address book always opens with the last selected contact
- **Calendar**: the quick event window opens next to the day or time you double-clicked, on the side facing the middle; context menus of events show no keyboard shortcuts; "for 2h" on the night clocks go back now really lasts two hours. Birthdays are a calendar in the calendar list – show or hide it with its checkbox
- **Tables**: the contact and task tables look like the mail table (font, row height, header, stripes, selection)
- **Message header**: the account's colour dot stands in front of the folder name, like in the folder list
- **Spaces button**: the Show/Hide Spaces button shows the space colours
- **Settings → halo.spaces** shows only what can't be set directly in the window; design, icons and logging are grouped under "Troubleshooting". Locked fields in dialogs (e.g. the name of the personal address book) now look locked

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

3. That's it. On first install halo.spaces sets **Themes** to **System theme – auto**
   (Thunderbird's default), so light and dark follow macOS. Thunderbird's Light or
   Dark stay if you chose one; themes from the add-on store paint their own colours
   over the design.

No restart is needed – the design is active right away.

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

Options
-------
Options that belong to a view are set right there: preview lines under
**View → Preview Lines**, contact photos in the list's **…** menu, and the
Birthdays calendar is shown or hidden with its checkbox in the calendar list.
All other options – sender logos, photos from the Contacts app, calendar
emojis, dialogs, updates, the bundled design and icons – are in
**Settings → halo.spaces** (also reachable via **Help → halo.spaces… →
Settings…** or **Add-ons and Themes → halo.spaces → Settings**). Changes take
effect right away unless noted.

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
