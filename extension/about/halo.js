// Halo Spaces – Info-Fenster. Texte und Knöpfe verbindet die Erweiterung,
// sobald das Fenster geladen ist (die Seite selbst hat keine Sonderrechte).
"use strict";

window.addEventListener("keydown", event => {
  if (event.key == "Escape") {
    window.close();
  }
});
