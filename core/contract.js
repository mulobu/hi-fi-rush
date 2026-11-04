/* core/contract.js -- the names every overlay shares (docs/adr/0004).

   Loaded by the pages as a script, and read as JSON by tools/obs-setup.py
   and start.py: everything after the "=" up to the final "}" must stay
   strict JSON -- double quotes, no comments, no trailing commas. */
window.OVERLAY_CONTRACT = {
  "scenes": ["START", "CHAT", "GAME", "CAM", "BRB", "END"],
  "host": { "main": "COMIC", "vertical": "VCOMIC" },
  "sources": {
    "game": "Game",
    "browser": "Browser",
    "cam": "Cam",
    "chat": "Chat",
    "overlay": "Overlay",
    "overlayVertical": "OverlayV",
    "mascot": "Mascot",
    "mascotVertical": "MascotV",
    "tts": "Tts",
    "discord": "Discord"
  },
  "ports": { "obs": 4455, "mascot": 4460, "chat": 4461, "heart": 4462 },
  "socials": [
    { "handle": "thedeepeffect", "on": ["kick"] },
    { "handle": "thedeepeffect_", "on": ["twitch", "youtube"] },
    { "handle": "@thedeepeffect__", "on": ["instagram"] }
  ],
  "socialNames": {
    "kick": "Kick",
    "twitch": "Twitch",
    "youtube": "YouTube",
    "instagram": "Instagram"
  }
};
