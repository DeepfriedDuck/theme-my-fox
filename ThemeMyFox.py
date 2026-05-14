import os
from pathlib import Path
import tempfile
import configparser
import json
import lz4.block

FIREFOX_PATH = Path(f"/home/{os.getenv("USER")}/.mozilla/firefox")
config = configparser.ConfigParser()
config.read(FIREFOX_PATH / "profiles.ini")
sections = config.sections()

def compress(src, dest):
    with open(src, "rb") as file:
        compressed = lz4.block.compress(file.read())
        output_file = b"mozLz40\0" + compressed
    with open(dest, "wb") as file:
        file.write(output_file)

def decompress(src, dest):
    with open(src, "rb") as file:
        if file.read(8) != b"mozLz40\0":
            raise ValueError("Invalid magic number")
        string_to_write = lz4.block.decompress(file.read())
    with open(dest, "wb") as file:
        file.write(string_to_write)

print("Please select an Profile:")
for section in sections:
    if not config.has_option(section, "Path"):
        config.remove_section(section)
sections = config.sections()

for section in sections:
    print(f"{sections.index(section)+1}:{config.get(section, "Name")}")
selected_profile_index = int(input("Please select an profile:"))

print("\n"*30)
###### Important line ##########
profile_path = FIREFOX_PATH / config.get(sections[selected_profile_index-1], "Path")
###### Now it begins ###########
#get availeble themes
available_themes = []
try:
    with open(profile_path / "addons.json", "r") as file:
        json_content = json.loads(file.read())
        for addon in json_content["addons"]:
            if addon["type"] == "theme":
                available_themes.append(addon)
except FileNotFoundError:
    print("Sorry no addon found in this profile")
for theme in available_themes:
    print(f"{available_themes.index(theme)+1}:{theme["name"]}")
selected_theme_index = int(input("Please select an theme:"))
selected_theme_addon_object = available_themes[selected_theme_index-1]

print(f"setting up {selected_theme_addon_object["name"]}")
selected_theme_id = selected_theme_addon_object["id"]
#####setting up theme in prefs.js######
prefs_js_path = profile_path / "prefs.js"
new_prefs_js_content = ""
with open(prefs_js_path, "r") as file:
    for line in file.readlines():
        if 'user_pref("extensions.activeThemeID", "' in line:
            new_prefs_js_content += f'user_pref("extensions.activeThemeID", "{selected_theme_id}");\n'
        else:
            new_prefs_js_content += line
with open(prefs_js_path, "w") as file:
    file.write(new_prefs_js_content)
##### setting up theme in extensions.json#########
extension_json_path = profile_path / "extensions.json"
with open(extension_json_path, "r") as file:
    json_content = json.loads(file.read())
    for addon in json_content["addons"]:
        if addon["id"] == selected_theme_id:
            json_content["addons"][json_content["addons"].index(addon)]["userDisabled"] = False
            json_content["addons"][json_content["addons"].index(addon)]["active"] = True
        else:
            json_content["addons"][json_content["addons"].index(addon)]["userDisabled"] = True
            json_content["addons"][json_content["addons"].index(addon)]["active"] = False
with open(extension_json_path, "w") as file:
    file.write(json.dumps(json_content))

##### setting addonStartup.json.lz4 #######
addon_startup_path = Path(tempfile.gettempdir()) / "addonStartup.json"
decompress(profile_path / "addonStartup.json.lz4", addon_startup_path)
with open(addon_startup_path, "r") as file:
    json_content = json.loads(file.read())
    for addon in json_content["app-profile"]["addons"]:
        if addon == selected_theme_id:
            json_content["app-profile"]["addons"][addon]["enabled"] = True
        else:
            json_content["app-profile"]["addons"][addon]["enabled"] = False
with open(addon_startup_path, "w") as file:
    file.write(json.dumps(json_content))
compress(addon_startup_path, profile_path / "addonStartup.json.lz4")