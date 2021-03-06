#!/usr/bin/python2.6

# This file is a part of Metagam project.
#
# Metagam is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# Metagam is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Metagam.  If not, see <http://www.gnu.org/licenses/>.

from mg import *
import re
import random

re_bad_symbols = re.compile(r'([^\w\- \.,:])', re.UNICODE)
re_bad_english_symbols = re.compile(r'([^a-z0-9A-Z\-_ \.,:])')
re_module_action = re.compile(r'^(enable|disable)/([a-z0-9\-]+)$')
re_invalid_colon = re.compile(r' :|:[^ ]')

class Game(Module):
    def register(self):
        self.rhook("menu-admin-root.index", self.menu_root_index)
        self.rhook("menu-admin-game.index", self.menu_game_index)
        self.rhook("ext-admin-game.profile", self.ext_profile, priv="game.profile")
        self.rhook("headmenu-admin-game.profile", self.headmenu_profile)
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("admin-game.recommended-actions", self.recommended_actions)
        self.rhook("headmenu-admin-game.logo", self.headmenu_logo)
        self.rhook("ext-admin-game.logo", self.ext_logo, priv="game.logo")
        self.rhook("headmenu-admin-game.modules", self.headmenu_modules)
        self.rhook("ext-admin-game.modules", self.ext_modules, priv="project.admin")
        self.rhook("ext-admin-game.lang", self.ext_lang, priv="game.lang")
        self.rhook("headmenu-admin-game.lang", self.headmenu_lang)

    def recommended_actions(self, recommended_actions):
        req = self.req()
        if req.has_access("game.profile"):
            if not self.conf("gameprofile.description"):
                recommended_actions.append({"icon": "/st/img/exclamation.png", "content": u'%s <hook:admin.link href="game/profile" title="%s" />' % (self._("Your game has no configured description. Before publishing your game you must provide a relevant description."), self._("Open the game profile")), "order": 0, "before_launch": True})

    def menu_root_index(self, menu):
        menu.append({"id": "game.index", "text": self._("Game"), "order": 20})
        req = self.req()
        if req.has_access("project.admin"):
            menu.append({"id": "game/modules", "text": self._("Game system modules"), "leaf": True, "order": 1, "icon": "/st-mg/menu/modules.png?3"})

    def permissions_list(self, perms):
        perms.append({"id": "game.lang", "name": self._("Game language editor")})
        perms.append({"id": "game.profile", "name": self._("Game profile editor")})
        perms.append({"id": "game.logo", "name": self._("Game logo editor")})

    def menu_game_index(self, menu):
        req = self.req()
        if req.has_access("game.lang"):
            menu.append({"id": "game/lang", "text": self._("Language"), "leaf": True, "order": 0, "icon": "/st-mg/menu/language.png"})
        if req.has_access("game.profile"):
            menu.append({"id": "game/profile", "text": self._("Profile"), "leaf": True, "order": 10, "even_unpublished": True, "icon": "/st-mg/menu/profile.png"})
        if req.has_access("game.logo"):
            menu.append({"id": "game/logo", "text": self._("Logo"), "leaf": True, "order": 20, "even_unpublished": True, "icon": "/st-mg/menu/icon.png?1"})

    def headmenu_profile(self, args):
        return self._("Game profile")

    def ext_profile(self):
        req = self.req()
        project = self.app().project
        author_name = req.param("author_name").strip()
        description = req.param("description").strip()
        indexpage_description = req.param("indexpage_description").strip()
        indexpage_keywords = req.param("indexpage_keywords").strip()
        if not project.get("published") and not project.get("moderation"):
            title_full = req.param("title_full").strip()
            title_short = req.param("title_short").strip()
            title_code = req.param("title_code").strip()
            title_en = req.param("title_en").strip()
        lang = self.call("l10n.lang")
        if req.param("ok"):
            config = self.app().config_updater()
            errors = {}
            if not project.get("published") and not project.get("moderation"):
                if not title_full:
                    errors["title_full"] = self._("Enter full title")
                elif len(title_full) > 50:
                    errors["title_full"] = self._("Maximal length - 50 characters")
                else:
                    m = re_bad_symbols.search(title_full)
                    if m:
                        sym = m.group(1)
                        errors["title_full"] = self._("Bad symbols in the title: %s") % htmlescape(sym)
                    elif title_full.endswith("."):
                        errors["title_full"] = self._("Title must not end with a dot")
                    elif re_invalid_colon.search(title_full):
                        errors["title_full"] = self._("You must not have a space before a colon (:) and must have a space after a colon (:)")
                if not title_short:
                    errors["title_short"] = self._("Enter short title")
                elif len(title_short) > 30:
                    errors["title_short"] = self._("Maximal length - 30 characters")
                else:
                    m = re_bad_symbols.search(title_short)
                    if m:
                        sym = m.group(1)
                        errors["title_short"] = self._("Bad symbols in the title: %s") % htmlescape(sym)
                    elif title_short.endswith("."):
                        errors["title_short"] = self._("Title must not end with a dot")
                    elif re_invalid_colon.search(title_short):
                        errors["title_short"] = self._("You must not have a space before a colon (:) and must have a space after a colon (:)")
                if not title_code:
                    errors["title_code"] = self._("Enter code")
                elif len(title_code) > 5:
                    errors["title_code"] = self._("Maximal length - 5 characters")
                elif re.match(r'[^a-z0-9A-Z]', title_code):
                    errors["title_code"] = self._("You can use digits and latin letters only")
                if lang != "en":
                    if not title_en:
                        errors["title_en"] = self._("Enter game title in English")
                    elif len(title_en) > 50:
                        errors["title_en"] = self._("Maximal length - 50 characters")
                    else:
                        m = re_bad_english_symbols.search(title_en)
                        if m:
                            sym = m.group(1)
                            errors["title_en"] = self._("Bad symbols in the title: %s") % htmlescape(sym)
                        elif title_en.endswith("."):
                            errors["title_en"] = self._("Title must not end with a dot")
                        elif re_invalid_colon.search(title_en):
                            errors["title_en"] = self._("You must not have a space before a colon (:) and must have a space after a colon (:)")
            if not description:
                errors["description"] = self._("Game description must not be empty")
            if len(errors):
                self.call("web.response_json", {"success": False, "errors": errors})
            with self.lock(["project.%s" % project.uuid]):
                project.load()
                config.set("gameprofile.author_name", author_name)
                config.set("gameprofile.description", description)
                config.set("gameprofile.indexpage_description", indexpage_description)
                config.set("gameprofile.indexpage_keywords", indexpage_keywords)
                if not project.get("published") and not project.get("moderation"):
                    project.set("title_full", title_full)
                    project.set("title_short", title_short)
                    project.set("title_code", title_code)
                    if lang == "en":
                        project.set("title_en", title_short)
                    else:
                        project.set("title_en", title_en)
                    project.store()
                config.store()
                self.call("admin.response", self._("Game profile stored"), {})
        else:
            author_name = self.conf("gameprofile.author_name")
            description = self.conf("gameprofile.description")
            indexpage_description = self.conf("gameprofile.indexpage_description")
            indexpage_keywords = self.conf("gameprofile.indexpage_keywords")
            title_full = project.get("title_full")
            title_short = project.get("title_short")
            title_code = project.get("title_code")
            if lang != "en":
                title_en = project.get("title_en")
        fields = []
        if not project.get("published") and not project.get("moderation"):
            fields.append({"name": "title_full", "label": self._("Full official game title (must start from capital letter, must not be in caps letter, must not be an abbreviation)"), "value": title_full})
            fields.append({"name": "title_short", "label": self._("Short game title for displaying in the games catalog (must start from capital letter, must not be in caps letter, must not be an abbreviation)"), "value": title_short})
            fields.append({"name": "title_code", "label": self._("Game code (should be an abbreviation)"), "value": title_code})
            if lang != "en":
                fields.append({"name": "title_en", "label": self._("Short game title in English for displaying in the payment system interface (must start from capital letter, must not be in caps letter, must not be an abbreviation)"), "value": title_en})
        fields.append({"name": "author_name", "label": self._("Game author name"), "value": author_name})
        fields.append({"type": "textarea", "name": "description", "label": self._("Game description"), "value": description})
        fields.append({"name": "indexpage_description", "label": self._("SEO HTML description for the index page"), "value": indexpage_description})
        fields.append({"name": "indexpage_keywords", "label": self._("SEO HELP keywords for the index page"), "value": indexpage_keywords})
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('Brief description of this form you can find in the <a href="//www.%s/doc/newgame#profile" target="_blank">reference manual</a>.') % self.main_host})
        self.call("admin.form", fields=fields)

    def headmenu_lang(self, args):
        return self._("Game language")

    def ext_lang(self):
        req = self.req()
        project = self.app().project
        if req.param("ok"):
            errors = {}
            # lang
            lang = req.param("v_lang")
            if lang != "en" and lang != "ru":
                errors["v_lang"] = self._("Invalid language")
            # process errors
            if errors:
                self.call("web.response_json", {"success": False, "errors": errors})
            # store
            with self.lock(["project.%s" % project.uuid]):
                project.load()
                project.set("lang", lang);
                project.store();
            self.call("cluster.appconfig_changed")
            self.call("config.changed")
            self.call("admin.redirect_top", "/admin?_rand=%s#game/lang" % random.random())
        # show form
        lang = self.call("l10n.lang")
        fields = []
        languages = []
        languages.append(("en", self._("English")))
        languages.append(("ru", self._("Russian")))
        fields.append({"name": "lang", "type": "combo", "label": self._("Game language"), "value": lang, "values": languages})
        self.call("admin.form", fields=fields)

    def ext_logo(self):
        req = self.req()
        project = self.app().project
        if project.get("published"):
            change = self._("Your project is published already. You can't change the game logo")
        elif project.get("moderation"):
            change = self._("Your project is on moderation now. You can't change the game logo")
        else:
            change = u'%s<br /><hook:admin.link href="game/logo/change" title="%s" />' % (self._("You will lose the ability to change the logo after game launch."), self._("Change the game logo now"))
            if req.args == "change":
                if req.ok():
                    self.call("web.upload_handler")
                    image = req.param_raw("image")
                    uri = self.call("admin-logo.uploader", image, project.get("title_short"))
                    with self.lock(["project.%s" % project.uuid]):
                        project.load()
                        if not project.get("published") and not project.get("moderation"):
                            project.set("logo", uri)
                            project.store()
                            self.app().store_config_hooks()
                    self.call("web.response_json_html", {"success": True, "redirect": "game/logo"})
                fields = []
                fields.append({"name": "image", "type": "fileuploadfield", "label": self._("Basic image for your logo")})
                buttons = [{"text": self._("Upload")}]
                self.call("admin.form", fields=fields, modules=["FileUploadField"], buttons=buttons)
        vars = {
            "CurrentLogo": self._("Current logo"),
            "logo": project.get("logo"),
            "change": change
        }
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('Brief description of the logo uploading you can find in the <a href="//www.%s/doc/newgame#logo" target="_blank">reference manual</a>.') % self.main_host})
        self.call("admin.response_template", "admin/game/logo.html", vars)

    def headmenu_logo(self, args):
        if args == "change":
            return [self._("Logo editor"), "game/logo"]
        return self._("Game logo")

    def render_modules(self, modules, rows, parent=None, padding=0):
        for mod in modules:
            if not mod.get("shown") and mod.get("parent") == parent:
                mod["shown"] = True
                status = self.conf("module.%s" % mod["id"])
                rows.append([
                    '<div class="%s" style="padding-left: %spx; white-space: nowrap">%s</div>' % ("admin-enabled" if status else "admin-disabled", padding, mod["name"]),
                    mod["description"],
                    '<hook:admin.link href="game/modules/disable/%s" title="%s" />' % (mod["id"], self._("disable")) if status else '<hook:admin.link href="game/modules/enable/%s" title="%s" />' % (mod["id"], self._("enable")),
                ])
                self.render_modules(modules, rows, mod["id"], padding + 30)

    def ext_modules(self):
        req = self.req()
        m = re_module_action.match(req.args)
        if m:
            action, module = m.group(1, 2)
            config = self.app().config_updater()
            config.set("module.%s" % module, True if action == "enable" else False)
            config.store()
            self.call("admin.redirect", "game/modules")
        modules = []
        self.call("modules.list", modules)
        modules.sort(cmp=lambda x, y: cmp(x.get("name"), y.get("name")))
        rows = []
        self.render_modules(modules, rows)
        vars = {
            "tables": [
                {
                    "header": [
                        self._("Module"),
                        self._("Description"),
                        self._("Action"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.advice", {"title": self._("Documentation"), "content": self._('Module structure of the constructor is described in the <a href="//www.%s/doc/modules" target="_blank">modules documentation</a>.') % self.main_host})
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def headmenu_modules(self, args):
        return self._("Game modules")

