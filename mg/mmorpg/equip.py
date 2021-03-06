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

from mg.constructor import *
from mg.mmorpg.inventory import MemberInventory, Item
from mg.mmorpg.inventory_classes import dna_parse, dna_join, DBItemTransfer
import re
import cStringIO
from PIL import Image

class EquipError(ScriptRuntimeError):
    pass

max_slot_id = 100
re_del = re.compile(r'^del/(\d+)$')
re_parse_dimensions = re.compile(r'^(\d+)x(\d+)$')
re_slot_token = re.compile(r'^slot-(\d+):(-?\d+),(-?\d+),(\d+),(\d+)$')
re_charimage_token = re.compile(r'^charimage:(-?\d+),(-?\d+),(\d+),(\d+)$')
re_staticimage_token = re.compile(r'^staticimage-([a-f0-9]{32})\((//.+)\):(-?\d+),(-?\d+),(\d+),(\d+)$')
re_aggregate = re.compile(r'^(sum|min|max|cnt_dna|cnt)_(.+)')
re_equip_slot = re.compile(r'^(\d+)$')
re_equip_slot_item = re.compile(r'^(\d+)/([a-f0-9]{32}|[a-f0-9]{32}_[a-f0-9]{32})$')
re_equip_item = re.compile(r'^([a-z0-9\-]+)/([a-f0-9_]+)$')
re_slot_id = re.compile(r'^slot([1-9][0-9]*)$')

class EquipItem(Item):
    def __init__(self, app, equip, slot, fqn="mg.mmorpg.equip.EquipItem"):
        item_type = equip.equipped(slot)
        if not item_type:
            raise EquipError(self._("Slot %s is not equipped") % slot, None)
        Item.__init__(self, app, item_type, equip.inv, fqn)
        self.equip = equip
        self.slot = slot

    def _set_param(self, *args, **kwargs):
        item_type = self.equip.equipped(self.slot)
        if not item_type or item_type.dna != self.dna:
            raise EquipError(self._("EquipItem is invalid at this point"), None)
        Item._set_param(self, *args, **kwargs)
        self.equip.equip(self.slot, self.item_type, call_events=False)

class MemberEquipInventory(MemberInventory):
    def __init__(self, app, owtype, uuid):
        ConstructorModule.__init__(self, app, "mg.mmorpg.equip.MemberEquipInventory")
        self.owtype = owtype
        self.uuid = uuid

    def load(self):
        MemberInventory.load(self)
        try:
            delattr(self, "_equipped_cache")
        except AttributeError:
            pass

    def _inv_update(self):
        MemberInventory._inv_update(self)
        self._equipped(use_cache=False)

    def _equip_data(self):
        if not getattr(self, "inv", None):
            self.load()
        eqp = self.inv.get("equip")
        if eqp is None:
            eqp = {
                "slots": {},
                "dna": {},
            }
            self.inv.set("equip", eqp)
        return eqp

    def _equipped(self, use_cache=True):
        if use_cache:
            try:
                return self._equipped_cache
            except AttributeError:
                pass
        equip_data = self._equip_data()
        eqp = {}
        update_equip = False
        for item in self._items():
            dna = dna_join(item.get("type"), item.get("dna"))
            quantity = item.get("quantity")
            slots = equip_data["dna"].get(dna)
            if slots:
                item_type = self.item_type(item.get("type"), item.get("dna"), item.get("mod"))
                for slot_id in slots:
                    if quantity > 0:
                        quantity -= 1
                        eqp[slot_id] = item_type
                    else:
                        # if equipped items count is greater than inventory count
                        # clear some slots
                        try:
                            del equip_data["slots"][slot_id]
                        except KeyError:
                            pass
                        update_equip = True
        if update_equip:
            self._update_equip_data()
        self._equipped_cache = eqp
        return eqp

    def _update_equip_data(self):
        equip_data = self._equip_data()
        dna_cnt = {}
        slots_copy = equip_data["slots"].copy()
        # looking for items in the slots
        for slot in self.call("equip.slots"):
            slot_id = str(slot["id"])
            dna = slots_copy.get(slot_id)
            if dna:
                try:
                    dna_cnt[dna].append(slot_id)
                except KeyError:
                    dna_cnt[dna] = [slot_id]
                del slots_copy[slot_id]
        # removing unclaimed slots from equip data
        for missing_slot_id in slots_copy.keys():
            del equip_data["slots"][missing_slot_id]
        equip_data["dna"] = dna_cnt
        try:
            delattr(self, "_equipped_cache")
        except AttributeError:
            pass
        self.inv.touch()

    def items(self, available_only=False):
        items = MemberInventory.items(self, available_only)
        if available_only:
            equip_data = self._equip_data()["dna"]
            new_items = []
            for item_type, quantity in items:
                equipped = equip_data.get(item_type.dna)
                if equipped:
                    quantity -= len(equipped)
                if quantity > 0:
                    new_items.append((item_type, quantity))
            items = new_items
        return items

    def find_dna(self, dna):
        item_type, quantity = MemberInventory.find_dna(self, dna)
        if not item_type:
            return None, None
        quantity -= len(self._equip_data()["dna"].get(dna, []))
        if quantity <= 0:
            return None, None
        return item_type, quantity

    def _aggregate(self, aggregate, param, handle_exceptions=True):
        value = MemberInventory._aggregate(self, aggregate, param, handle_exceptions)
        if aggregate == "cnt":
            # looking for item types quantity
            equipped_cnt = 0
            for dna, slots in self._equip_data()["dna"].iteritems():
                tp = dna_parse(dna)[0]
                if tp == param:
                    equipped_cnt += len(slots)
            value -= equipped_cnt
            if value < 0:
                value = 0
        elif aggregate == "cnt_dna":
            # looking for item dna quantity
            equipped_cnt = 0
            for dna, slots in self._equip_data()["dna"].iteritems():
                if dna == param:
                    equipped_cnt += len(slots)
            value -= equipped_cnt
            if value < 0:
                value = 0
        return value

    def _item_changed(self, old_item_type, new_item_type):
        equip_data = self._equip_data()
        slots = equip_data["dna"].get(old_item_type)
        if not slots:
            return
        item_type, quantity = MemberInventory.find_dna(self, old_item_type)
        if not quantity:
            quantity = 0
        if quantity >= len(slots):
            return
        inv_slots = equip_data["slots"]
        while quantity < len(slots):
            slot = slots.pop()
            if new_item_type:
                inv_slots[slot] = new_item_type
                new_item_type = None
            else:
                try:
                    del inv_slots[slot]
                except KeyError:
                    pass
        self._update_equip_data()

class CharacterEquip(ConstructorModule):
    def __init__(self, character):
        ConstructorModule.__init__(self, character.app(), "mg.mmorpg.equip.CharacterEquip")
        self.character = character
        self.inv = character.inventory

    def equipped_items(self):
        return self.inv._equipped().values()

    def equipped_slots(self):
        return self.inv._equipped().items()

    def equipped(self, slot_id):
        return self.inv._equipped().get(str(slot_id))

    def equip(self, slot_id, item_type, drop_event="equip-unwear", call_events=True):
        equip_data = self.inv._equip_data()
        slot_id = str(slot_id)
        equipped = equip_data["slots"].get(slot_id)
        if equipped:
            equipped_item, quantity = MemberInventory.find_dna(self.inv, equipped)
            if not equipped_item:
                equipped = None
        if item_type:
            if equipped:
                if equipped_item.dna != item_type.dna:
                    if call_events:
                        self.event(drop_event, slot=int(slot_id), item=EquipItem(self.app(), self, slot_id))
                    equip_data["slots"][slot_id] = item_type.dna
                    self.inv._update_equip_data()
                    if call_events:
                        self.event("equip-wear", slot=int(slot_id), item=EquipItem(self.app(), self, slot_id))
            else:
                equip_data["slots"][slot_id] = item_type.dna
                self.inv._update_equip_data()
                if call_events:
                    self.event("equip-wear", slot=int(slot_id), item=EquipItem(self.app(), self, slot_id))
        else:
            try:
                del equip_data["slots"][slot_id]
            except KeyError:
                pass
            else:
                self.inv._update_equip_data()
                if equipped and call_events:
                    self.event(drop_event, slot=int(slot_id), item=equipped_item)
        self._invalidate()
        self.inv._invalidate()
        self.character._invalidate()

    def break_item(self, slot, fractions, description=None, **kwargs):
        """
        Breaks item in the given slot for the specified number of fractions.
        Doesn't store/validate inventory. Need to do equip.validate(), inv.store()
        manually.
        """
        equip_data = self.inv._equip_data()
        dna = equip_data["slots"].get(slot)
        if dna is None:
            return None, None
        # 1. unequip the item
        del equip_data["slots"][slot]
        self.inv._update_equip_data()
        # 2. take DNA
        item, quantity = self.inv._take_dna(dna, 1)
        if not quantity or not item:
            return None, None
        # 3. increase "used"
        new_item_type = item.item_type.copy()
        if not new_item_type.mods:
            new_item_type.mods = {}
        used = new_item_type.mods.get(":used", 0)
        max_fractions = new_item_type.get("fractions", 1)
        if used + fractions >= max_fractions:
            # discard item
            spent = max_fractions - used
            destroyed = True
            new_item_type = None
        else:
            spent = fractions
            destroyed = False
            # 4. give new DNA
            new_item_type.mods[":used"] = used + fractions
            new_item_type.update_dna()
            self.inv._give(new_item_type.uuid, 1, mod=new_item_type.mods)
            # 5. equip the item
            equip_data["slots"][slot] = new_item_type.dna
            self.inv._update_equip_data()
        # log the operation
        if description:
            performed = kwargs.get("performed") or self.now()
            trans = self.obj(DBItemTransfer)
            trans.set("owner", self.inv.uuid)
            if self.inv.owtype != "char":
                trans.set("owtype", self.inv.owtype)
            trans.set("type", item.item_type.uuid)
            if item.item_type.dna_suffix:
                trans.set("dna", item.item_type.dna_suffix)
                trans.set("mod", item.item_type.mods)
            trans.set("quantity", -1)
            trans.set("description", description)
            for k, v in kwargs.iteritems():
                trans.set(k, v)
            trans.set("performed", performed)
            self.inv.trans.append(trans)
            if new_item_type:
                data = trans.data
                trans = self.obj(DBItemTransfer)
                trans.data = data.copy()
                trans.set("dna", new_item_type.dna_suffix)
                trans.set("mod", new_item_type.mods)
                trans.set("quantity", 1)
                self.inv.trans.append(trans)
        return spent, destroyed

    @property
    def char_params(self):
        try:
            return self._char_params
        except AttributeError:
            pass
        params = self.call("characters.params")
        self._char_params = params
        return params

    def cannot_equip(self, item_type):
        char = self.character
        for param in self.char_params:
            key = "min-%s" % param["code"]
            min_val = item_type.get(key)
            if min_val is not None:
                val = char.param(param["code"])
                if val is None or val < min_val:
                    name = param.get("name")
                    name_g = param.get("name_g", name)
                    return self._("param///{name} is not enough to wear {item_name}").format(name=name, name_g=name_g, item_name=item_type.name, item_name_a=item_type.name_a)
        if not self.call("script.evaluate-expression", item_type.get("wear_cond", 1), globs={"char": char, "item": item_type}, description=lambda: self._("Whether item {item} ({name}) is wearable").format(item=item_type.uuid, name=item_type.name)):
            return self._("You can't wear {item_name} at the moment").format(item_name=item_type.name, item_name_a=item_type.name_a)
        return None

    def script_attr(self, attr, handle_exceptions=True):
        # aggregates
        m = re_aggregate.match(attr)
        if m:
            aggregate, param = m.group(1, 2)
            return self.aggregate(aggregate, param, handle_exceptions)
        m = re_slot_id.match(attr)
        if m:
            slot_id = m.group(1)
            slot_id = int(slot_id)
            item_type = self.equipped(slot_id)
            if item_type:
                item_type = EquipItem(self.app(), self, slot_id)
            return item_type
        raise AttributeError(attr)

    def aggregate(self, aggregate, param, handle_exceptions=True):
        key = "%s-%s" % (aggregate, param)
        # trying to return cached value
        try:
            cache = self._item_aggregate_cache
        except AttributeError:
            cache = {}
            self._item_aggregate_cache = cache
        try:
            return cache[key]
        except KeyError:
            pass
        # cache miss. evaluating
        if aggregate == "cnt":
            # looking for item types quantity
            value = 0
            now = self.now()
            for item_type in self.equipped_items():
                if item_type.uuid == param:
                    if not item_type.expiration or now <= item_type.expiration:
                        value += 1
        elif aggregate == "cnt_dna":
            # looking for item dna quantity
            value = 0
            now = self.now()
            for item_type in self.equipped_items():
                if item_type.dna == param:
                    if not item_type.expiration or now <= item_type.expiration:
                        value += 1
        else:
            # looking for items parameters
            if aggregate == "sum":
                value = 0
            else:
                value = None
            for item_type in self.equipped_items():
                v = nn(item_type.param(param, handle_exceptions))
                if v is not None:
                    if value is None:
                        value = v
                    elif aggregate == "min":
                        if v < value:
                            value = v
                    elif aggregate == "max":
                        if v > value:
                            value = v
                    elif aggregate == "sum":
                        value += v
        # storing in the cache
        cache[key] = value
        return value

    def _invalidate(self):
        try:
            delattr(self, "_item_aggregate_cache")
        except AttributeError:
            pass

    def has_invalid_items(self):
        changed = False
        equip_data = self.inv._equip_data()
        slots = equip_data["slots"]
        for slot in self.call("equip.slots"):
            item_type = self.equipped(slot["id"])
            if item_type and self.cannot_equip(item_type):
                changed = True
                continue
            if not item_type and slots.get(str(slot["id"])):
                del slots[str(slot["id"])]
                changed = True
        if changed:
            self.inv._update_equip_data()
        return changed

    def validate(self):
        "Validate character equip"
        retry = True
        changed = False
        while retry:
            retry = False
            for slot in self.call("equip.slots"):
                item_type = self.equipped(slot["id"])
                if item_type:
                    error = self.cannot_equip(item_type)
                    if error:
                        self.character.error(error)
                        self.equip(slot["id"], None, drop_event="equip-drop")
                        self._invalidate()
                        self.inv._invalidate()
                        self.character._invalidate()
                        retry = True
                        changed = True
        return changed

    def event(self, ident, **kwargs):
        if not getattr(self, "events", None):
            self.events = []
        kwargs["char"] = self.character
        self.events.append({
            "id": ident,
            "args": kwargs,
        })

    def fire_events(self):
        if not getattr(self, "events", None):
            return
        for event in self.events:
            self.qevent(event["id"], **event["args"])
        self.events = []

class EquipAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("menu-admin-inventory.index", self.menu_inventory_index)
        self.rhook("menu-admin-equip.index", self.menu_equip_index)
        self.rhook("headmenu-admin-equip.slots", self.headmenu_slots)
        self.rhook("ext-admin-equip.slots", self.admin_slots, priv="equip.config")
        self.rhook("admin-item-types.form-render", self.item_type_form_render)
        self.rhook("admin-item-types.form-validate", self.item_type_form_validate)
        self.rhook("admin-item-types.dimensions", self.item_type_dimensions)
        self.rhook("headmenu-admin-equip.layout", self.headmenu_layout)
        self.rhook("ext-admin-equip.layout", self.admin_layout, priv="equip.config")
        self.rhook("admin-storage.group-names", self.group_names)
        self.rhook("admin-storage.nondeletable", self.nondeletable)
        self.rhook("advice-admin-equip.index", self.advice_equip)
        self.rhook("advice-admin-item-types.index", self.advice_equip)
        self.rhook("admin-gameinterface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "item-hint.html", "description": self._("Item mouse over hint"), "doc": "/doc/equip"})

    def advice_equip(self, hook, args, advice):
        advice.append({"title": self._("Equipment documentation"), "content": self._('You can find detailed information on the characters equipment system in the <a href="//www.%s/doc/equip" target="_blank">equipment page</a> in the reference manual.') % self.main_host, "order": 20})

    def nondeletable(self, uuids):
        interfaces = self.call("equip.interfaces")
        for iface in interfaces:
            layout = self.conf("equip.layout-%s" % iface["id"])
            if layout:
                images = layout.get("images")
                if images:
                    for img in images:
                        uuids.add(img["uuid"])

    def group_names(self, group_names):
        group_names["equip-layout"] = self._("Equipment layout")

    def permissions_list(self, perms):
        perms.append({"id": "equip.config", "name": self._("Characters equipment configuration")})

    def menu_inventory_index(self, menu):
        menu.append({"id": "equip.index", "text": self._("Equipment"), "order": 50})

    def menu_equip_index(self, menu):
        req = self.req()
        if req.has_access("equip.config"):
            menu.append({"id": "equip/slots", "text": self._("Equipment slots"), "order": 0, "leaf": True})
            menu.append({"id": "equip/layout", "text": self._("Equipment layouts"), "order": 10, "leaf": True})

    def headmenu_slots(self, args):
        if args == "new":
            return [self._("New slot"), "equip/slots"]
        elif valid_nonnegative_int(args):
            return [self._("Slot %s") % args, "equip/slots"]
        return self._("Equipment slots")

    def admin_slots(self):
        req = self.req()
        slots = self.call("equip.slots")
        interfaces = self.call("equip.interfaces")
        # deletion
        m = re_del.match(req.args)
        if m:
            sid = intz(m.group(1))
            slots = [slot for slot in slots if slot["id"] != sid]
            config = self.app().config_updater()
            config.set("equip.slots", slots)
            config.store()
            self.call("admin.redirect", "equip/slots")
        # editing
        if req.args:
            if req.args == "new":
                sid = self.conf("equip.max-slot", 0) + 1
                if sid > max_slot_id:
                    sid = None
                order = None
                for s in slots:
                    if order is None or s["order"] > order:
                        order = s["order"]
                order = 0.0 if order is None else order + 10.0
                slot = {
                    "id": sid,
                    "order": order,
                }
            else:
                sid = intz(req.args)
                slot = None
                for s in slots:
                    if s["id"] == sid:
                        slot = s
                        break
                if not slot:
                    self.call("admin.redirect", "equip/slots")
            if req.ok():
                self.call("web.upload_handler")
                slot = slot.copy()
                errors = {}
                upload = []
                delete_images = []
                # id
                sid = req.param("id").strip()
                if not sid:
                    errors["id"] = self._("This field is mandatory")
                elif not valid_nonnegative_int(sid):
                    errors["id"] = self._("Slot ID must be a nonnegative integer in range 1-%d") % max_slot_id
                else:
                    sid = intz(sid)
                    if sid < 1:
                        errors["id"] = self._("Minimal value is %d") % 1
                    elif sid > max_slot_id:
                        errors["id"] = self._("Maximal value is %d") % max_slot_id
                    elif sid != slot["id"]:
                        for s in slots:
                            if s["id"] == sid:
                                errors["id"] = self._("Slot with this ID already exists")
                # order
                slot["order"] = floatz(req.param("order"))
                # name
                name = req.param("name").strip()
                if not name:
                    errors["name"] = self._("This field is mandatory")
                else:
                    slot["name"] = name
                # description
                description = req.param("description").strip()
                if not description:
                    errors["description"] = self._("This field is mandatory")
                else:
                    slot["description"] = description
                # interfaces
                for iface in interfaces:
                    key = "iface-%s" % iface["id"]
                    if req.param(key):
                        slot[key] = True
                        key_size = "ifsize-%s" % iface["id"]
                        dim = req.param(key_size).strip()
                        m = re_parse_dimensions.match(dim)
                        if not m:
                            errors[key_size] = self._("Invalid dimensions format")
                        else:
                            width, height = m.group(1, 2)
                            width = int(width)
                            height = int(height)
                            if width < 16 or height < 16:
                                errors[key_size] = self._("Minimal size is 16x16")
                            elif width > 128 or height > 128:
                                errors[key_size] = self._("Maximal size is 128x128")
                            else:
                                slot[key_size] = [width, height]

                            # Image should be parsed only if dimensions are defined
                            key_empty = "ifempty-%s" % iface["id"]
                            if req.param("ifdelempty-%s" % iface["id"]):
                                if key_empty in slot:
                                    delete_images.append(slot[key_empty])
                                    del slot[key_empty]
                            else:
                                image_data = req.param_raw(key_empty)
                                if image_data:
                                    try:
                                        image = Image.open(cStringIO.StringIO(image_data))
                                        if image.load() is None:
                                            raise IOError
                                    except IOError:
                                        errors[key_empty] = self._("Image format not recognized")
                                    else:
                                        ext, content_type = self.image_format(image)
                                        form = image.format
                                        trans = image.info.get("transparency")
                                        w, h = image.size
                                        if ext is None:
                                            errors[key_empty] = self._("Valid formats are: PNG, GIF, JPEG")
                                        elif w != width or h != height:
                                            errors[key_empty] = self._("Dimensions of the image must match slot dimensions ({width}x{height} uploaded, {ewidth}x{eheight} expected)").format(width=w, height=h, ewidth=width, eheight=height)
                                        else:
                                            data = cStringIO.StringIO()
                                            if form == "JPEG":
                                                image.save(data, form, quality=95)
                                            elif form == "GIF":
                                                if trans:
                                                    image.save(data, form, transparency=trans)
                                                else:
                                                    image.save(data, form)
                                            else:
                                                image.save(data, form)
                                            upload.append((slot, key_empty, image, ext, content_type, data))
                    else:
                        slot[key] = False
                # visible
                char = self.character(req.user())
                slot["visible"] = self.call("script.admin-expression", "visible", errors, globs={"char": char})
                # enabled
                slot["available"] = self.call("script.admin-expression", "available", errors, globs={"char": char})
                # handle errors
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # upload images
                for slot, key, image, ext, content_type, data in upload:
                    uri = self.call("cluster.static_upload", "item", ext, content_type, data.getvalue())
                    delete_images.append(slot.get(key))
                    slot[key] = uri
                # storing
                slots = [s for s in slots if s["id"] != slot["id"]]
                slot["id"] = sid
                slots.append(slot)
                slots.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["id"], y["id"]))
                config = self.app().config_updater()
                if sid > self.conf("equip.max-slot", 0):
                    config.set("equip.max-slot", sid)
                config.set("equip.slots", slots)
                config.store()
                # delete old images
                for uri in delete_images:
                    if uri:
                        self.call("cluster.static_delete", uri)
                self.call("admin.redirect", "equip/slots")
            fields = [
                {"label": self._("Slot ID (integer number)"), "name": "id", "value": slot.get("id")},
                {"label": self._("Sorting order"), "name": "order", "value": slot.get("order"), "inline": True},
                {"label": self._("Slot name"), "name": "name", "value": slot.get("name")},
                {"label": self._("Description (ex: Slot for summoning scrolls)"), "name": "description", "value": slot.get("description")},
                {"label": self._("Visibility condition") + self.call("script.help-icon-expressions"), "name": "visible", "value": self.call("script.unparse-expression", slot.get("visible", 1))},
                {"label": self._("Availability condition") + self.call("script.help-icon-expressions"), "name": "available", "value": self.call("script.unparse-expression", slot.get("available", 1))},
                {"type": "header", "html": self._("slot///Visibility in the interfaces")},
            ]
            for iface in interfaces:
                key = "iface-%s" % iface["id"]
                fields.append({"name": key, "label": iface["title"], "type": "checkbox", "checked": slot.get(key)})
                key_size = "ifsize-%s" % iface["id"]
                size = slot.get(key_size, [60, 60])
                fields.append({"name": key_size, "label": self._("Slot dimensions (ex: 60x60)"), "value": "%dx%d" % (size[0], size[1]), "condition": "[%s]" % key})
                key_empty = "ifempty-%s" % iface["id"]
                if slot.get(key_empty):
                    fields.append({"type": "checkbox", "name": "ifdelempty-%s" % iface["id"], "label": self._("Delete empty slot image")})
                    fields.append({"name": key_empty, "label": (u'<p><img src="%s" alt="" /></p>' % slot[key_empty]) + self._("Replace empty slot image"), "type": "fileuploadfield", "condition": "[%s] && ![ifdelempty-%s]" % (key, iface["id"])})
                else:
                    fields.append({"name": key_empty, "label": self._("Empty slot image"), "type": "fileuploadfield", "condition": "[%s]" % key})
            self.call("admin.form", fields=fields, modules=["FileUploadField"])
        rows = []
        for slot in slots:
            rows.append([
                htmlescape(slot["id"]),
                htmlescape(slot["name"]),
                u'<hook:admin.link href="equip/slots/%s" title="%s" />' % (slot["id"], self._("edit")),
                u'<hook:admin.link href="equip/slots/del/%s" title="%s" confirm="%s" />' % (slot["id"], self._("delete"), self._("Are you sure want to delete this slot?")),
            ])
        vars = {
            "tables": [
                {
                    "links": [
                        {"hook": "equip/slots/new", "text": self._("New slot"), "lst": True},
                    ],
                    "header": [
                        self._("Slot ID"),
                        self._("Slot name"),
                        self._("Editing"),
                        self._("Deletion"),
                    ],
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def item_type_form_render(self, obj, fields):
        pos = len(fields)
        for i in xrange(0, len(fields)):
            if fields[i].get("mark") == "categories":
                pos = i
                break
        fields.insert(pos, {"type": "header", "html": self._("Equipment")})
        pos += 1
        fields.insert(pos, {"type": "checkbox", "label": self._("This item is wearable"), "name": "equip", "checked": obj.get("equip")})
        pos += 1
        fields.insert(pos, {"label": self._("Script condition whether this item can be worn") + self.call("script.help-icon-expressions"), "name": "wear_cond", "value": self.call("script.unparse-expression", obj.get("wear_cond", 1)), "condition": "[equip]"})
        pos += 1
        fields.insert(pos, {"label": self._("Script condition whether this item can be undressed") + self.call("script.help-icon-expressions"), "name": "unwear_cond", "value": self.call("script.unparse-expression", obj.get("unwear_cond", 1)), "condition": "[equip]", "inline": True})
        pos += 1
        fields.insert(pos, {"label": self._("Script condition whether this item has 'wear' button") + self.call("script.help-icon-expressions"), "name": "equip_wear", "value": self.call("script.unparse-expression", obj.get("equip_wear", 1)), "condition": "[equip]"})
        pos += 1
        fields.insert(pos, {"type": "empty", "inline": True})
        pos += 1
        fields.insert(pos, {"label": self._("'Wear' button title"), "name": "equip_wear_title", "value": obj.get("equip_wear_title", self._("wear")), "condition": "[equip]"})
        pos += 1
        fields.insert(pos, {"label": self._("'Unwear' prompt"), "name": "equip_unwear_title", "value": obj.get("equip_unwear_title", self._("Click to unequip")), "condition": "[equip]", "inline": True})
        pos += 1
        # checkboxes
        slots = self.call("equip.slots")
        col = 0
        cols = 3
        while col < len(slots):
            slot = slots[col]
            key = "equip-%s" % slot["id"]
            fields.insert(pos, {"name": key, "type": "checkbox", "label": "%s (%s)" % (slot["name"], slot["id"]), "checked": obj.get(key), "inline": col % cols, "condition": "[equip]"})
            pos += 1
            col += 1
        while col % cols:
            fields.insert(pos, {"type": "empty", "inline": True})
            pos += 1
            col += 1
        # requirements
        fields.insert(pos, {"type": "header", "html": self._("Minimal requirements to wear this item"), "condition": "[equip]"})
        pos += 1
        params = self.call("characters.params")
        if params:
            col = 0
            cols = 3
            for param in params:
                key = "min-%s" % param["code"]
                fields.insert(pos, {"name": key, "label": htmlescape(param["name"]), "value": obj.get(key), "inline": col % cols, "condition": "[equip]"})
                pos += 1
                col += 1
            while col % cols:
                fields.insert(pos, {"type": "empty", "inline": True})
                pos += 1
                col += 1
        else:
            fields.insert(pos, {"type": "html", "html": self._("Characters parameters are not defined")})
            pos += 1

    def item_type_form_validate(self, obj, errors):
        req = self.req()
        if req.param("equip"):
            obj.set("equip", True)
            for slot in self.call("equip.slots"):
                key = "equip-%s" % slot["id"]
                if req.param(key):
                    obj.set(key, True)
                else:
                    obj.delkey(key)
            for param in self.call("characters.params"):
                key = "min-%s" % param["code"]
                val = req.param(key).strip()
                if val != "":
                    if not valid_number(val):
                        errors[key] = self._("This is not a valid number")
                    else:
                        obj.set(key, nn(val))
                else:
                    obj.delkey(key)
            char = self.character(req.user())
            obj.set("equip_wear", self.call("script.admin-expression", "equip_wear", errors, globs={"char": char}))
            obj.set("wear_cond", self.call("script.admin-expression", "wear_cond", errors, globs={"char": char}))
            obj.set("unwear_cond", self.call("script.admin-expression", "unwear_cond", errors, globs={"char": char}))
            # equip_wear_title
            equip_wear_title = req.param("equip_wear_title").strip()
            if not equip_wear_title:
                errors["equip_wear_title"] = self._("This field is mandatory")
            else:
                obj.set("equip_wear_title", equip_wear_title)
            # equip_unwear_title
            equip_unwear_title = req.param("equip_unwear_title").strip()
            if not equip_unwear_title:
                errors["equip_unwear_title"] = self._("This field is mandatory")
            else:
                obj.set("equip_unwear_title", equip_unwear_title)
        else:
            obj.delkey("equip")

    def item_type_dimensions(self, obj, dimensions):
        if obj.get("equip"):
            existing = set(["%dx%d" % (d["width"], d["height"]) for d in dimensions])
            for slot in self.call("equip.slots"):
                key = "equip-%s" % slot["id"]
                if obj.get(key):
                    for iface in self.call("equip.interfaces"):
                        key_size = "ifsize-%s" % iface["id"]
                        dim = slot.get(key_size) or [60, 60]
                        key_size = "%dx%d" % (dim[0], dim[1])
                        if not key_size in existing:
                            existing.add(key_size)
                            dimensions.append({"width": dim[0], "height": dim[1]})

    def headmenu_layout(self, args):
        if args:
            for iface in self.call("equip.interfaces"):
                if iface["id"] == args:
                    return [iface["title"], "equip/layout"]
        return self._("Equipment layouts")

    def admin_layout(self):
        req = self.req()
        if req.args:
            iface = None
            for i in self.call("equip.interfaces"):
                if i["id"] == req.args:
                    iface = i
                    break
            if not iface:
                self.call("admin.redirect", "equip/layout")
            slots = self.call("equip.slots")
            if req.ok():
                layout = {}
                min_x = None
                min_y = None
                max_x = None
                max_y = None
                errors = {}
                error = None
                # grid
                if req.param("grid"):
                    grid_size = req.param("grid_size")
                    if valid_nonnegative_int(grid_size):
                        grid_size = int(grid_size)
                        if grid_size <= 1:
                            layout["grid"] = 1
                        elif grid_size > 50:
                            layout["grid"] = 50
                        else:
                            layout["grid"] = grid_size
                else:
                    layout["grid"] = 0
                # slot_border
                slot_border = intz(req.param("slot_border"))
                if slot_border < 0:
                    slot_border = 0
                elif slot_border > 50:
                    slot_border = 50
                layout["slot-border"] = slot_border
                # charimage_border
                charimage_border = intz(req.param("charimage_border"))
                if charimage_border < 0:
                    charimage_border = 0
                elif charimage_border > 50:
                    charimage_border = 50
                layout["charimage-border"] = charimage_border
                # coords
                images = []
                for token in req.param("coords").split(";"):
                    m = re_slot_token.match(token)
                    if m:
                        slot_id, x, y, width, height = m.group(1, 2, 3, 4, 5)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        layout["slot-%s-x" % slot_id] = x
                        layout["slot-%s-y" % slot_id] = y
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    m = re_charimage_token.match(token)
                    if m:
                        x, y, width, height = m.group(1, 2, 3, 4)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        layout["char-x"] = x
                        layout["char-y"] = y
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    m = re_staticimage_token.match(token)
                    if m:
                        uuid, uri, x, y, width, height = m.group(1, 2, 3, 4, 5, 6)
                        x = int(x)
                        y = int(y)
                        width = int(width)
                        height = int(height)
                        images.append({
                            "uuid": uuid,
                            "uri": uri,
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                        })
                        min_x = min2(x, min_x)
                        min_y = min2(y, min_y)
                        max_x = max2(x + width, max_x)
                        max_y = max2(y + height, max_y)
                        continue
                    error = self._("Unknown token: %s" % htmlescape(token))
                if error:
                    self.call("web.response_json", {"success": False, "error": error})
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                # storing
                if images:
                    layout["images"] = images
                if min_x is not None:
                    layout["min_x"] = min_x
                    layout["min_y"] = min_y
                    layout["width"] = max_x - min_x
                    layout["height"] = max_y - min_y
                config = self.app().config_updater()
                config.set("equip.layout-%s" % iface["id"], layout)
                config.store()
                self.call("admin.redirect", "equip/layout")
            layout = self.conf("equip.layout-%s" % iface["id"], {})
            vars = {
                "ie_warning": self._("Warning! Internet Explorer browser is not supported. Equipment layout editor may work slowly and unstable. Text rendering is not supported in IE. Mozilla Firefox, Google Chrome and Opera are fully supported."),
                "submit_url": "/admin-equip/layout/%s" % iface["id"],
                "grid_size": layout.get("grid", iface["grid"]),
                "slot_border": layout.get("slot-border", 1),
                "charimage_border": layout.get("charimage-border", 0),
            }
            if not self.conf("module.storage"):
                vars["storage_unavailable"] = jsencode(self._("To access this function you need to enable 'Static Storage' system module"))
            elif not req.has_access("storage.static"):
                vars["storage_unavailable"] = jsencode(self._("You don't have permission to upload objects to the static storage"))
            # slots
            rslots = []
            for slot in slots:
                if slot.get("iface-%s" % iface["id"]):
                    dim = slot.get("ifsize-%s" % iface["id"]) or [60, 60]
                    rslots.append({
                        "id": slot["id"],
                        "name": jsencode(slot["name"]),
                        "x": layout.get("slot-%d-x" % slot["id"], 0),
                        "y": layout.get("slot-%d-y" % slot["id"], 0),
                        "width": dim[0],
                        "height": dim[1],
                    })
            vars["slots"] = rslots;
            # character image
            dim = self.call(iface["dim_hook"])
            if dim:
                m = re_parse_dimensions.match(dim)
                if m:
                    width, height = m.group(1, 2)
                    width = int(width)
                    height = int(height)
                    vars["charimage"] = {
                        "x": layout.get("char-x", 0),
                        "y": layout.get("char-y", 0),
                        "width": width,
                        "height": height,
                    }
            # static images
            images = layout.get("images")
            if images:
                rimages = []
                for img in images:
                    rimages.append({
                        "uuid": img["uuid"],
                        "uri": jsencode(img["uri"]),
                        "x": img["x"],
                        "y": img["y"],
                        "width": img["width"],
                        "height": img["height"],
                    })
                vars["staticimages"] = rimages
            # rendering
            self.call("admin.response_template", "admin/equip/layout.html", vars)
        rows = []
        interfaces = self.call("equip.interfaces")
        for iface in interfaces:
            rows.append([u'<hook:admin.link href="equip/layout/%s" title="%s" />' % (iface["id"], iface["title"])])
        vars = {
            "tables": [
                {
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

def min2(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a < b:
        return a
    else:
        return b

def max2(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a > b:
        return a
    else:
        return b

class Equip(ConstructorModule):
    def register(self):
        self.rhook("equip.slots", self.slots)
        self.rhook("equip.interfaces", self.interfaces)
        self.rhook("character-page.render", self.character_page_render)
        self.rhook("character-info.render", self.character_info_render)
        self.rhook("ext-equip.slot", self.equip_slot, priv="logged")
        self.rhook("ext-unequip.slot", self.unequip_slot, priv="logged")
        self.rhook("inventory.get", self.inventory_get, priority=10)
        self.rhook("item-types.params-owner-important", curry(self.params_generation, "page"), priority=-20)
        self.rhook("item-types.params-owner-all", curry(self.params_generation, "page"), priority=-20)
        self.rhook("item-types.params-public", curry(self.params_generation, "info"), priority=-20)
        self.rhook("equip.get", self.equip_get)
        self.rhook("items.menu", self.items_menu)
        self.rhook("ext-equip.item", self.equip_item, priv="logged")

    def child_modules(self):
        return ["mg.mmorpg.equip.EquipAdmin"]

    def slots(self):
        return self.conf("equip.slots", [])

    def interfaces(self):
        interfaces = [
            {
                "id": "char-owner",
                "title": self._("Internal game interface for character owner"),
                "dim_hook": "charimages.dim-charpage",
                "grid": 5,
                "show_actions": True,
            },
            {
                "id": "char-public",
                "title": self._("Public character info"),
                "dim_hook": "charimages.dim-charinfo",
                "grid": 10,
            },
        ]
        return interfaces

    def character_page_render(self, character, vars):
        self.render_layout("char-owner", character, vars)

    def character_info_render(self, character, vars):
        self.render_layout("char-public", character, vars)

    def render_layout(self, iface_id, character, vars):
        # validating character equip
        equip = character.equip
        inv = character.inventory
        if character.equip.has_invalid_items():
            with self.lock([inv.lock_key]):
                equip.validate()
                inv.store()
            equip.fire_events()
            character.name_invalidate()
            self.call("quest.check-redirects")
        # rendering layout
        for iface in self.interfaces():
            if iface["id"] == iface_id:
                layout = self.conf("equip.layout-%s" % iface_id)
                if layout:
                    slot_border = layout.get("slot-border", 1)
                    charimage_border = layout.get("charimage-border", 0)
                    border = max(slot_border, charimage_border)
                    offset_x = border
                    offset_y = border
                    items = []
                    # static images
                    images = layout.get("images")
                    if images:
                        for image in images:
                            items.append({
                                "x": image["x"] + offset_x,
                                "y": image["y"] + offset_y,
                                "width": image["width"],
                                "height": image["height"],
                                "cls": "equip-static-image",
                                "border": 0,
                                "image": {
                                    "src": image["uri"],
                                },
                            })
                    # characer image
                    dim = self.call(iface["dim_hook"])
                    if dim:
                        m = re_parse_dimensions.match(dim)
                        if m:
                            width, height = m.group(1, 2)
                            width = int(width)
                            height = int(height)
                            items.append({
                                "x": layout.get("char-x", 0) + offset_x,
                                "y": layout.get("char-y", 0) + offset_y,
                                "width": width,
                                "height": height,
                                "cls": "charimage-background equip-char-image",
                                "border": charimage_border,
                                "image": {
                                    "src": vars["avatar_image"],
                                },
                            })
                    # slots
                    design = None
                    equip = character.equip
                    for slot in self.slots():
                        # visibility of the slot in this interface
                        if not slot.get("iface-%s" % iface_id):
                            continue
                        item_type = equip.equipped(slot["id"])
                        # global visibility of the slot
                        if not item_type and not self.call("script.evaluate-expression", slot.get("visible", 1), {"char": character}, description=self._("Visibility of slot '%s'") % slot["name"]):
                            continue
                        # rendering
                        size = slot.get("ifsize-%s" % iface_id)
                        ritem = {
                            "x": layout.get("slot-%s-x" % slot["id"], 0) + offset_x,
                            "y": layout.get("slot-%s-y" % slot["id"], 0) + offset_y,
                            "width": size[0],
                            "height": size[1],
                            "cls": "equip-slot equip-%s-%s" % (character.uuid, slot["id"]),
                            "border": slot_border,
                        }
                        if iface.get("show_actions"):
                            ritem["cls"] += " clickable"
                        if item_type:
                            if not design:
                                design = self.design("gameinterface")
                            ritem["image"] = {
                                "src": item_type.image("%dx%d" % (size[0], size[1])),
                            }
                            ritem["onclick"] = "return Game.main_open('/unequip/slot/%s');" % slot["id"]
                            # rendering hint with item parameters
                            hint_vars = {
                                "item": {
                                    "name": htmlescape(item_type.name),
                                    "description": item_type.get("description"),
                                },
                            }
                            params = []
                            self.call("item-types.params-owner-important", item_type, params)
                            if params:
                                for param in params:
                                    if param.get("library_icon"):
                                        del param["library_icon"]
                                params[-1]["lst"] = True
                                hint_vars["item"]["params"] = params
                            if iface.get("show_actions"):
                                hint_vars["hint"] = item_type.get("equip_unwear_title", self._("Click to unequip"))
                            ritem["hint"] = {
                                "cls": "equip-%s-%s" % (character.uuid, slot["id"]),
                                "html": jsencode(self.call("design.parse", design, "item-hint.html", None, hint_vars)),
                            }
                        else:
                            description = slot.get("description")
                            ritem["hint"] = {
                                "cls": "equip-%s-%s" % (character.uuid, slot["id"]),
                            }
                            img = slot.get("ifempty-%s" % iface_id)
                            if img:
                                ritem["image"] = {
                                    "src": img
                                }
                            if description:
                                ritem["hint"]["html"] = jsencode(description)
                            if self.call("script.evaluate-expression", slot.get("available", 1), {"char": character}, description=self._("Availability of slot '%s'") % slot["name"]):
                                if iface.get("show_actions"):
                                    ritem["onclick"] = "return Game.main_open('/equip/slot/%s');" % slot["id"]
                            else:
                                ritem["cls"] += " equip-slot-disabled"
                                if description:
                                    ritem["hint"]["html"] = u"%s<br />%s" % (jsencode(description), self._("Slot is currently unavailable"))
                                else:
                                    ritem["hint"]["html"] = self._("Slot is currently unavailable")
                        items.append(ritem)
                    cur_y = 0
                    for item in items:
                        item["x"] = item["x"] - layout["min_x"] - item["border"]
                        item["y"] = item["y"] - layout["min_y"] - cur_y - item["border"]
                        cur_y += item["height"] + item["border"] * 2
                    rlayout = {
                        "width": layout["width"] + border * 2,
                        "height": layout["height"] + border * 2,
                        "items": items,
                    }
                    vars["equip_layout"] = rlayout
                    if not vars.get("load_extjs"):
                        vars["load_extjs"] = {}
                    vars["load_extjs"]["qtips"] = True

    def inventory_get(self, owtype, uuid):
        if owtype == "char":
            raise Hooks.Return(MemberEquipInventory(self.app(), owtype, uuid))

    def equip_slot(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        if character.busy:
            character.error(self._("You are busy and cannot equip yourself at the moment"))
            self.call("web.redirect", "/interface/character")
        inv = character.inventory 
        equip = character.equip
        # parsing request
        m = re_equip_slot.match(req.args)
        if m:
            slot_id = m.group(1)
            slot_id = int(slot_id)
            dna = None
        else:
            m = re_equip_slot_item.match(req.args)
            if m:
                slot_id, dna = m.group(1, 2)
                slot_id = int(slot_id)
            else:
                self.call("web.redirect", "/interface/character")
        # loading slot data
        for slot in self.call("equip.slots"):
            if slot["id"] == slot_id:
                # visibility and availability of the slot
                if not self.call("script.evaluate-expression", slot.get("visible", 1), {"char": character}, description=self._("Visibility of slot '%s'") % slot["name"]):
                    break
                if not self.call("script.evaluate-expression", slot.get("available", 1), {"char": character}, description=self._("Availability of slot '%s'") % slot["name"]):
                    break
                # actions
                if dna is None:
                    # looking for items to dress
                    vars = {}
                    def grep(item_type):
                        return item_type.get("equip") and item_type.get("equip-%s" % slot_id) and not equip.cannot_equip(item_type)
                    def render(item_type, ritem):
                        menu = []
                        menu.append({"href": "/equip/slot/%s/%s" % (slot["id"], item_type.dna), "html": item_type.get("equip_wear_title", self._("wear")), "order": 10})
                        if menu:
                            menu[-1]["lst"] = True
                            ritem["menu"] = menu
                        ritem["onclick"] = "return parent.Game.main_open('/equip/slot/%s/%s')" % (slot["id"], item_type.dna)
                    self.call("inventory.render", inv, vars, grep=grep, render=render, viewer=character)
                    vars["title"] = slot.get("description") or slot["name"]
                    vars["menu_left"] = [
                        {
                            "href": "/interface/character",
                            "html": self._("Character"),
                        }, {
                            "html": slot["name"],
                            "lst": True
                        }
                    ]
                    if not vars["categories"]:
                        character.error(self._("You don't have items to fit into this slot"))
                        self.call("web.redirect", "/interface/character")
                    self.call("game.response_internal", "inventory.html", vars)
                else:
                    with self.lock([inv.lock_key]):
                        if equip.equipped(slot_id):
                            self.call("web.redirect", "/interface/character")
                        item_type, quantity = inv.find_dna(dna)
                        if not quantity:
                            character.error(self._("No such item"))
                            self.call("web.redirect", "/interface/character")
                        if not item_type.get("equip"):
                            character.error(self._("This item is not wearable"))
                            self.call("web.redirect", "/interface/character")
                        if not item_type.get("equip-%s" % slot_id):
                            character.error(self._("This item is not wearable in this slot"))
                            self.call("web.redirect", "/interface/character")
                        error = equip.cannot_equip(item_type)
                        if error:
                            character.error(error)
                            self.call("web.redirect", "/interface/character")
                        equip.equip(slot_id, item_type)
                        equip.validate()
                        inv.store()
                    equip.fire_events()
                    character.name_invalidate()
                    self.call("quest.check-redirects")
                    self.call("web.redirect", "/interface/character")
        character.error(self._("This slot is currently unavailable"))
        self.call("web.redirect", "/interface/character")

    def unequip_slot(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        if character.busy:
            character.error(self._("You are busy and cannot equip yourself at the moment"))
            self.call("web.redirect", "/interface/character")
        m = re_equip_slot.match(req.args)
        if m:
            slot_id = m.group(1)
            slot_id = int(slot_id)
        character = self.character(req.user())
        inv = character.inventory
        equip = character.equip
        with self.lock([inv.lock_key]):
            item = equip.equipped(slot_id)
            if item:
                if not self.call("script.evaluate-expression", item.get("unwear_cond", 1), globs={"char": character, "item": item}, description=lambda: self._("Whether an item {item} ({name}) can be undressed").format(item=item.uuid, name=item.name)):
                    character.error(self._("This item can't be undressed"))
                    self.call("web.redirect", "/interface/character")
                equip.equip(slot_id, None)
                equip.validate()
                inv.store()
        equip.fire_events()
        character.name_invalidate()
        self.call("quest.check-redirects")
        self.call("web.redirect", "/interface/character")

    def params_generation(self, cls, obj, params, viewer=None, **kwargs):
        if obj.get("equip"):
            # requirements
            need_header = True
            for param in self.call("characters.params"):
                key = "min-%s" % param["code"]
                min_val = obj.get(key)
                if min_val is not None:
                    if need_header:
                        params.append({
                            "header": self._("Requirements"),
                            "important": True,
                        })
                        need_header = False
                    value_html = self.call("characters.param-html", param, min_val)
                    if viewer and viewer.param(param["code"]) < min_val:
                        value_html = u'<span class="not-enough">%s</span>' % value_html
                    params.append({
                        "value_raw": min_val,
                        "name": '<span class="item-types-%s-name">%s</span>' % (cls, htmlescape(param["name"])),
                        "value": '<span class="item-types-%s-value">%s</span>' % (cls, value_html),
                        "library_icon": self.call("characters.library-icon", param),
                    })

    def equip_get(self, character):
        return CharacterEquip(character)

    def items_menu(self, character, item_type, menu):
        if item_type.get("equip"):
            if self.call("script.evaluate-expression", item_type.get("equip_wear", 1), globs={"char": character, "item": item_type}, description=lambda: self._("Whether 'wear' button is available on the item {item} ({name})").format(item=item_type.uuid, name=item_type.name)):
                menu.append({"href": "/equip/item/%s/%s" % (item_type.cat("inventory"), item_type.dna), "html": htmlescape(item_type.get("equip_wear_title", self._("wear"))), "order": 80})

    def equip_item(self):
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        if character.busy:
            character.error(self._("You are busy and cannot equip yourself at the moment"))
            self.call("web.redirect", "/interface/character")
        inv = character.inventory 
        equip = character.equip
        # parsing request
        m = re_equip_item.match(req.args)
        if not m:
            self.call("web.redirect", "/inventory")
        cat, dna = m.group(1, 2)
        def ret(error=None):
            if error:
                character.error(error)
            self.call("web.redirect", "/inventory?cat=%s#%s" % (cat, dna))
        # looking for matching items
        item_type, quantity = inv.find_dna(dna)
        if not quantity:
            ret(self._("You have no such items"))
        if not item_type.get("equip"):
            ret(self._("This item is not wearable"))
        if not self.call("script.evaluate-expression", item_type.get("equip_wear", 1), globs={"char": character, "item": item_type}, description=lambda: self._("Whether 'wear' button is available on the item {item} ({name})").format(item=item_type.uuid, name=item_type.name)):
            ret(self._("This item has no 'wear' button"))
        error = equip.cannot_equip(item_type)
        if error:
            ret(error)
        # looking for the best slot
        best_slot = None
        best_price = None
        rates = self.call("exchange.rates") or {}
        for slot in self.call("equip.slots"):
            slot_id = slot["id"]
            if item_type.get("equip-%s" % slot_id):
                equipped_item = equip.equipped(slot_id)
                if equipped_item:
                    # don't replace items with the same type
                    if equipped_item.uuid == item_type.uuid:
                        continue
                    # don't replace items that can't be undressed
                    if not self.call("script.evaluate-expression", equipped_item.get("unwear_cond", 1), globs={"char": character, "item": equipped_item}, description=lambda: self._("Whether an item {item} ({name}) can be undressed").format(item=equipped_item.uuid, name=equipped_item.name)):
                        continue
                    # if this slot is occupied. Trying to find the slot with minimal balance price
                    price = equipped_item.get("balance-price")
                    if price:
                        currency = equipped_item.get("balance-currency")
                        price *= rates.get(currency, 1)
                    else:
                        price = 0
                    # recording best price
                    if best_slot is None or price < best_price:
                        best_slot = slot_id
                        best_price = price
                else:
                    # visibility and availability of the slot
                    if self.call("script.evaluate-expression", slot.get("visible", 1), {"char": character}, description=self._("Visibility of slot '%s'") % slot["name"]):
                        if self.call("script.evaluate-expression", slot.get("available", 1), {"char": character}, description=self._("Availability of slot '%s'") % slot["name"]):
                            # If an empty available slot found, consider it the best match
                            best_slot = slot_id
                            break
        # checking for existence of slots
        if not best_slot:
            ret(self._("You have no more slots to wear this item type"))
        # equipping item
        with self.lock([inv.lock_key]):
            equip.equip(best_slot, item_type)
            equip.validate()
            inv.store()
        equip.fire_events()
        character.name_invalidate()
        self.call("quest.check-redirects")
        ret()

