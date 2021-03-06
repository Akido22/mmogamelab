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
from mg.mmorpg.inventory_classes import dna_parse
import re

default_sell_price = ["glob", "price"]
default_buy_price = ["*", ["*", ["glob", "price"], [".", ["glob", "item"], "frac_ratio"]], 0.1]

re_sell_item = re.compile(r'^sell-([a-f0-9]{32})$')
re_request_item = re.compile(r'^([a-f0-9_]+)/(\d+\.\d+|\d+)/([A-Z0-9]+)/(\d+)$')

re_stats_arg = re.compile(r'^(sell|buy)/([A-Z0-9a-z]+)/(\d\d\d\d-\d\d-\d\d)$')
re_valid_template = re.compile(r'^[a-zA-Z][a-zA-Z0-9\-]*\.html$')

class DBShopOperation(CassandraObject):
    clsname = "ShopOperation"
    indexes = {
        "performed": [[], "performed"],
    }

class DBShopOperationList(CassandraObjectList):
    objcls = DBShopOperation

class ShopsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("item-categories.list", self.item_categories_list)
        self.rhook("admin-interfaces.form", self.form_render)
        self.rhook("admin-interface-shop.store", self.form_store)
        self.rhook("admin-interface-shop.actions", self.actions)
        self.rhook("admin-interface-shop.action-assortment", self.assortment, priv="shops.config")
        self.rhook("admin-interface-shop.headmenu-assortment", self.headmenu_assortment)
        self.rhook("objclasses.list", self.objclasses_list)
        self.rhook("queue-gen.schedule", self.schedule)
        self.rhook("admin-shops.stats", self.stats)
        self.rhook("admin-item-types.dim-list", self.dim_list)
        self.rhook("menu-admin-economy.index", self.menu_economy_index)
        self.rhook("ext-admin-shops.stats", self.admin_stats, priv="shops.stat")
        self.rhook("headmenu-admin-shops.stats", self.headmenu_stats)
        self.rhook("advice-admin-shops.index", self.advice_shops)
        self.rhook("admin-gameinterface.design-files", self.design_files)

    def design_files(self, files):
        files.append({"filename": "shop-global.html", "description": self._("Shops interface template"), "doc": "/doc/shops"})
        files.append({"filename": "shop-items-layout.html", "description": self._("Shop assortment template"), "doc": "/doc/shops"})

    def advice(self):
        return {"title": self._("Shops documentation"), "content": self._('You can find detailed information on the shops system in the <a href="//www.%s/doc/shops" target="_blank">shops page</a> in the reference manual.') % self.main_host, "order": 50}

    def advice_shops(self, hook, args, advice):
        advice.append(self.advice())

    def dim_list(self, dimensions):
        dimensions.append({
            "id": "shops",
            "title": self._("Dimensions in shops"),
            "default": "60x60",
            "order": 30,
        })

    def schedule(self, sched):
        sched.add("admin-shops.stats", "8 0 * * *", priority=10)

    def objclasses_list(self, objclasses):
        objclasses["ShopOperation"] = (DBShopOperation, DBShopOperationList)

    def permissions_list(self, perms):
        perms.append({"id": "shops.config", "name": self._("Shops configuration")})
        perms.append({"id": "shops.stat", "name": self._("Shops statistics")})

    def item_categories_list(self, catgroups):
        catgroups.append({"id": "shops", "name": self._("Shops"), "order": 15, "description": self._("For goods being sold in shops")})

    def form_render(self, fields, func):
        fields.append({"name": "shop_sell", "label": self._("This shop sells goods"), "type": "checkbox", "checked": func.get("shop_sell"), "condition": "[tp] == 'shop'"})
        fields.append({"name": "shop_sell_price", "label": self._("Sell price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_sell_price", default_sell_price)), "condition": "[tp]=='shop' && [shop_sell]"})
        fields.append({"name": "shop_buy", "label": self._("This shop buys goods"), "type": "checkbox", "checked": func.get("shop_buy"), "condition": "[tp] == 'shop'"})
        fields.append({"name": "shop_buy_price", "label": self._("Buy price correction") + self.call("script.help-icon-expressions"), "value": self.call("script.unparse-expression", func.get("shop_buy_price", default_buy_price)), "condition": "[tp]=='shop' && [shop_buy]"})
        fields.append({"type": "header", "html": self._("Shop design"), "condition": "[tp]=='shop'"})
        fields.append({"name": "shop_template_default", "label": self._("Use default html template"), "type": "checkbox", "checked": func.get("shop_template") is None, "condition": "[tp]=='shop'"})
        fields.append({"name": "shop_template", "label": self._("Template name"), "value": func.get("shop_template", "shop-items-layout.html"), "condition": "[tp]=='shop' && ![shop_template_default]"})

    def form_store(self, func, errors):
        req = self.req()
        char = self.character(req.user())
        currencies = {}
        self.call("currencies.list", currencies)
        if currencies:
            currency = currencies.keys()[0]
        else:
            currency = "GOLD"
        item = self.call("admin-inventory.sample-item")
        # sell
        if req.param("shop_sell"):
            func["shop_sell"] = True
            func["shop_sell_price"] = self.call("script.admin-expression", "shop_sell_price", errors, globs={"char": char, "price": 1, "currency": currency, "item": item})
        else:
            func["shop_sell"] = False
        # buy
        if req.param("shop_buy"):
            func["shop_buy"] = True
            func["shop_buy_price"] = self.call("script.admin-expression", "shop_buy_price", errors, globs={"char": char, "price": 1, "currency": currency, "item": item})
        else:
            func["shop_buy"] = False
        if not func.get("shop_buy") and not func.get("shop_sell"):
            errors["v_tp"] = self._("Shop must either sell or buy goods (or both)")
        # default action
        if func.get("shop_sell"):
            func["default_action"] = "sell"
        elif func.get("shop_buy"):
            func["default_action"] = "buy"
        else:
            func["default_action"] = "sell"
        # design template
        if req.param("shop_template_default"):
            if "shop_template" in func:
                del func["shop_template"]
        else:
            tpl = req.param("shop_template").strip()
            if not tpl:
                errors["shop_template"] = self._("This field is mandatory")
            elif not re_valid_template.match(tpl):
                errors["shop_template"] = self._("Template name must start with latin letter. Other symbols may be latin letters, digits or '-'. File name extension must be .html")
            else:
                func["shop_template"] = tpl

    def actions(self, func_id, func, actions):
        req = self.req()
        actions.append({
            "id": "assortment",
            "text": self._("shop assortment"),
        })
        if req.has_access("inventory.track"):
            actions.append({
                "hook": "inventory/view/shop/{shop}".format(shop=func_id),
                "text": self._("shop store"),
            })

    def headmenu_assortment(self, func, args):
        if args:
            categories = self.call("item-types.categories", "admin")
            for cat in categories:
                if cat["id"] == args:
                    return [htmlescape(cat["name"]), "assortment"]
        return self._("Assortment of '%s'") % htmlescape(func["title"])

    def assortment(self, func_id, base_url, func, args):
        categories = self.call("item-types.categories", "admin")
        req = self.req()
        self.call("admin.advice", self.advice())
        if args:
            currencies = {}
            self.call("currencies.list", currencies)
            currencies_list = [(code, info["name_plural"]) for code, info in currencies.iteritems()]
            currencies_list.insert(0, (None, self._("currency///Auto")))
            item_types = []
            for item_type in self.item_types_all():
                cat = item_type.get("cat-admin")
                misc = None
                found = False
                for c in categories:
                    if c["id"] == cat:
                        found = True
                    elif cat is None and c.get("default"):
                        cat = c["id"]
                        found = True
                    if c.get("misc"):
                        misc = c["id"]
                if not found:
                    cat = misc
                if cat == args:
                    item_types.append(item_type)
            item_types.sort(cmp=lambda x, y: cmp(x.get("order", 0), y.get("order", 0)) or cmp(x.name, y.name))
            assortment = self.conf("shop-%s.assortment" % func_id, {})
            if req.ok():
                new_assortment = assortment.copy()
                errors = {}
                item = self.call("admin-inventory.sample-item")
                char = self.character(req.user())
                for item_type in item_types:
                    uuid = item_type.uuid
                    for tp in ["sell", "buy"]:
                        for key in ["%s-%s", "%s-store-%s", "%s-price-%s", "%s-currency-%s", "%s-available-%s"]:
                            key2 = key % (tp, uuid)
                            if key2 in new_assortment:
                                del new_assortment[key2]
                        if func.get("shop_%s" % tp) and req.param("%s-%s" % (tp, uuid)):
                            new_assortment["%s-%s" % (tp, uuid)] = True
                            new_assortment["%s-store-%s" % (tp, uuid)] = True if req.param("%s-store-%s" % (tp, uuid)) else False
                            curr = req.param("v_%s-currency-%s" % (tp, uuid))
                            if curr:
                                cinfo = currencies.get(curr)
                                if not cinfo:
                                    errors["v_%s-currency-%s" % (tp, uuid)] = self._("Make a valid selection")
                                else:
                                    new_assortment["%s-currency-%s" % (tp, uuid)] = curr
                            price = req.param("%s-price-%s" % (tp, uuid)).strip()
                            if price != "":
                                if not valid_nonnegative_float(price):
                                    errors["%s-price-%s" % (tp, uuid)] = self._("Invalid number format")
                                else:
                                    price = float(price)
                                    if price > 1000000:
                                        errors["%s-price-%s" % (tp, uuid)] = self._("Maximal value is %d") % 1000000
                                    else:
                                        new_assortment["%s-price-%s" % (tp, uuid)] = price
                                if curr == "":
                                    errors["v_%s-currency-%s" % (tp, uuid)] = self._("Currency is not specified")
                            key = "%s-available-%s" % (tp, uuid)
                            new_assortment[key] = self.call("script.admin-expression", key, errors, globs={"char": char, "item": item})
                if errors:
                    self.call("web.response_json", {"success": False, "errors": errors})
                config = self.app().config_updater()
                config.set("shop-%s.assortment" % func_id, new_assortment)
                config.store()
                self.call("admin.redirect", "%s/assortment" % base_url)
            fields = []
            for item_type in item_types:
                uuid = item_type.uuid
                fields.append({"type": "header", "html": htmlescape(item_type.name)})
                if func.get("shop_sell"):
                    fields.append({"type": "checkbox", "name": "sell-%s" % uuid, "checked": assortment.get("sell-%s" % uuid), "label": self._("Shop sells these items")})
                if func.get("shop_buy"):
                    fields.append({"type": "checkbox", "name": "buy-%s" % uuid, "checked": assortment.get("buy-%s" % uuid), "label": self._("Shop buys these items"), "inline": True})
                if func.get("shop_sell"):
                    fields.append({"name": "sell-store-%s" % uuid, "type": "checkbox", "checked": assortment.get("sell-store-%s" % uuid), "label": self._("Sell from the store only"), "condition": "[sell-%s]" % uuid})
                    fields.append({"name": "sell-price-%s" % uuid, "value": assortment.get("sell-price-%s" % uuid), "label": self._("Sell price"), "condition": "[sell-%s]" % uuid})
                    fields.append({"name": "sell-currency-%s" % uuid, "value": assortment.get("sell-currency-%s" % uuid), "label": self._("Sell currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[sell-%s]" % uuid})
                    fields.append({"name": "sell-available-%s" % uuid, "value": self.call("script.unparse-expression", assortment.get("sell-available-%s" % uuid, 1)), "label": self._("Availability for sell") + self.call("script.help-icon-expressions"), "condition": "[sell-%s]" % uuid, "inline": True})
                if func.get("shop_buy"):
                    fields.append({"name": "buy-store-%s" % uuid, "type": "checkbox", "checked": assortment.get("buy-store-%s" % uuid), "label": self._("Put bought items to the store"), "condition": "[buy-%s]" % uuid})
                    fields.append({"name": "buy-price-%s" % uuid, "value": assortment.get("buy-price-%s" % uuid), "label": self._("Buy price"), "condition": "[buy-%s]" % uuid})
                    fields.append({"name": "buy-currency-%s" % uuid, "value": assortment.get("buy-currency-%s" % uuid), "label": self._("Buy currency"), "type": "combo", "values": currencies_list, "inline": True, "condition": "[buy-%s]" % uuid})
                    fields.append({"name": "buy-available-%s" % uuid, "value": self.call("script.unparse-expression", assortment.get("buy-available-%s" % uuid, 1)), "label": self._("Availability for buy") + self.call("script.help-icon-expressions"), "condition": "[buy-%s]" % uuid, "inline": True})
            self.call("admin.advice", {"title": self._("Shop prices"), "content": self._("If a price is not specified balance price will be used. If currency is specified but price not then the balance price will be converted to the currency given")})
            self.call("admin.form", fields=fields)
        rows = []
        for cat in categories:
            rows.append([
                u'<hook:admin.link href="%s/assortment/%s" title="%s" />' % (base_url, cat["id"], htmlescape(cat["name"]))
            ])
        vars = {
            "tables": [
                {
                    "rows": rows,
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

    def stats(self):
        today = self.nowdate()
        yesterday = prev_date(today)
        lst = self.objlist(DBShopOperationList, query_index="performed", query_finish=today)
        lst.load(silent=True)
        operations = {}
        for ent in lst:
            shop = ent.get("shop")
            mode = ent.get("mode")
            ops = ent.get("operations")
            for dna, info in ops.iteritems():
                item_type, mods = dna_parse(dna)
                price = info.get("price")
                currency = info.get("currency")
                quantity = info.get("quantity")
                if item_type and price and quantity and currency:
                    key = "%s-%s-%s" % (shop, mode, currency)
                    try:
                        ops_list = operations[key]
                    except KeyError:
                        ops_list = {}
                        operations[key] = ops_list
                    amount = price * quantity
                    try:
                        ops_list[item_type][0] += amount
                        ops_list[item_type][1] += quantity
                    except KeyError:
                        ops_list[item_type] = [amount, quantity]
        if operations:
            self.call("dbexport.add", "shops_stats", date=yesterday, operations=operations)
        lst.remove()

    def menu_economy_index(self, menu):
        req = self.req()
        if req.has_access("shops.stat"):
            menu.append({"id": "shops/stats", "text": self._("Shops statistics"), "leaf": True, "order": 30})

    def headmenu_stats(self, args):
        m = re_stats_arg.match(args)
        if m:
            mode, currency, date = m.group(1, 2, 3)
            if mode == "sell":
                return [self._("Sales for {currency} at {date}").format(currency=currency, date=self.call("l10n.date_local", date)), "shops/stats"]
            elif mode == "buy":
                return [self._("Buyings for {currency} at {date}").format(currency=currency, date=self.call("l10n.date_local", date)), "shops/stats"]
        return self._("Shops statistics")

    def admin_stats(self):
        req = self.req()
        m = re_stats_arg.match(req.args)
        if m:
            mode, currency, date = m.group(1, 2, 3)
            data = {}
            for row in self.sql_read.selectall_dict("select item_type, sum(amount) as amount, sum(quantity) as quantity from shops_{mode} where app=? and period=? and currency=? group by item_type".format(mode=mode), self.app().tag, date, currency):
                data[row["item_type"]] = [nn(row["amount"]), nn(row["quantity"])]
            item_types = self.item_types_load(data.keys(), load_params=False)
            item_types.sort(cmp=lambda x, y: cmp(x.name, y.name))
            rows = []
            for item_type in item_types:
                info = data.get(item_type.uuid)
                if info:
                    rows.append([
                        htmlescape(item_type.name),
                        self.call("money.price-html", info[0], currency),
                        info[1],
                    ])
            vars = {
                "tables": [
                    {
                        "header": [
                            self._("Item type"),
                            self._("Volume of transactions"),
                            self._("Number of items"),
                        ],
                        "rows": rows
                    }
                ]
            }
            self.call("admin.response_template", "admin/common/tables.html", vars)
        dates = set()
        currencies = set()
        cols = set()
        operations = set()
        for mode in ["sell", "buy"]:
            for row in self.sql_read.selectall_dict("select date_format(period, '%Y-%m-%d') as d, currency from shops_{mode} where app=? group by d, currency".format(mode=mode), self.app().tag):
                dates.add(row["d"])
                currencies.add(row["currency"])
                cols.add("{currency}-{mode}".format(currency=row["currency"], mode=mode))
                operations.add("{d}-{currency}-{mode}".format(d=row["d"], currency=row["currency"], mode=mode))
        dates = sorted(list(dates))
        currencies = sorted(list(currencies))
        # Formatting header
        header = [self._("Date")]
        for cur in currencies:
            if "{currency}-sell".format(currency=cur) in cols:
                header.append(self._("Sales for %s") % cur)
            if "{currency}-buy".format(currency=cur) in cols:
                header.append(self._("Buyings for %s") % cur)
        # Formatting rows
        rows = []
        for date in dates:
            row = [self.call("l10n.date_local", date)]
            for cur in currencies:
                if "{currency}-sell".format(currency=cur) in cols:
                    if "{d}-{currency}-sell".format(d=date, currency=cur) in operations:
                        row.append(u'<hook:admin.link href="shops/stats/sell/%s/%s" title="%s" />' % (cur, date, self._("open")))
                    else:
                        row.append('')
                if "{currency}-buy".format(currency=cur) in cols:
                    if "{d}-{currency}-buy".format(d=date, currency=cur) in operations:
                        row.append(u'<hook:admin.link href="shops/stats/buy/%s/%s" title="%s" />' % (cur, date, self._("open")))
                    else:
                        row.append('')
            rows.append(row)
        vars = {
            "tables": [
                {
                    "header": header,
                    "rows": rows
                }
            ]
        }
        self.call("admin.response_template", "admin/common/tables.html", vars)

class Shops(ConstructorModule):
    def register(self):
        self.rhook("interfaces.list", self.interfaces_list)
        self.rhook("interface-shop.action-sell", self.sell, priv="logged")
        self.rhook("interface-shop.action-buy", self.buy, priv="logged")
        self.rhook("money-description.shop-buy", self.money_description_shop_buy)
        self.rhook("money-description.shop-sell", self.money_description_shop_sell)
        self.rhook("money-description.shop-bought", self.money_description_shop_bought)
        self.rhook("money-description.shop-sold", self.money_description_shop_sold)
        self.rhook("item-types.dim-shops", self.dim_shops)

    def dim_shops(self):
        return self.conf("item-types.dim_shops", "60x60")

    def money_description_shop_buy(self):
        return {
            "args": [],
            "text": self._("Shop buy"),
        }

    def money_description_shop_sell(self):
        return {
            "args": [],
            "text": self._("Shop sell"),
        }

    def money_description_shop_bought(self):
        return {
            "args": [],
            "text": self._("Bought by the shop"),
        }

    def money_description_shop_sold(self):
        return {
            "args": [],
            "text": self._("Sold by the shop"),
        }

    def child_modules(self):
        return ["mg.mmorpg.shops.ShopsAdmin"]

    def interfaces_list(self, types):
        types.append(("shop", self._("Shop")))

    def shop_tp_menu(self, func, base_url, args, vars):
        entries = []
        if func.get("shop_sell"):
            entries.append({
                "id": "sell",
                "html": self._("menu///Buy"),
            })
        if func.get("shop_buy"):
            entries.append({
                "id": "buy",
                "html": self._("menu///Sell"),
            })
        if len(entries) >= 2:
            for e in entries:
                if args != e["id"]:
                    e["href"] = "%s/%s" % (base_url, e["id"])
            entries[-1]["lst"] = True
            vars["shop_func_menu"] = entries

    def transaction(self, mode, func_id, base_url, func, args, vars):
        self.shop_tp_menu(func, base_url, mode, vars)
        vars["title"] = func.get("title")
        self.call("quest.check-dialogs")
        req = self.req()
        character = self.character(req.user())
        shop_inventory = self.call("inventory.get", "shop", func_id)
        # locking
        lock_objects = []
        if req.ok():
            lock_objects.append("ShopLock.%s" % func_id)
            lock_objects.append(character.lock)
            lock_objects.append(character.money.lock_key)
            lock_objects.append(character.inventory.lock_key)
            lock_objects.append(shop_inventory.lock_key)
        with self.lock(lock_objects):
            character.inventory.load()
            shop_inventory.load()
            # loading list of categories
            categories = self.call("item-types.categories", "shops")
            assortment = self.conf("shop-%s.assortment" % func_id, {})
            if mode == "sell":
                # loading shop store
                item_types = []
                max_quantity = {}
                for item_type, quantity in shop_inventory.items():
                    if assortment.get("sell-%s" % item_type.uuid) and assortment.get("sell-store-%s" % item_type.uuid):
                        item_types.append(item_type)
                        max_quantity[item_type.dna] = quantity
                # loading list of unlimited items to sell
                item_type_uuids = []
                for key in assortment.keys():
                    m = re_sell_item.match(key)
                    if not m:
                        continue
                    uuid = m.group(1)
                    if not assortment.get("sell-store-%s" % uuid):
                        item_type_uuids.append(uuid)
                # loading unlimited item types data
                item_types.extend(self.item_types_load(item_type_uuids))
            else:
                # loading character's inventory
                item_types = []
                max_quantity = {}
                for item_type, quantity in character.inventory.items(available_only=True):
                    if assortment.get("buy-%s" % item_type.uuid):
                        item_types.append(item_type)
                        max_quantity[item_type.dna] = quantity
            # user action
            if req.ok():
                if character.busy:
                    character.error(self._("You are busy and cannot do shopping at the moment"))
                    self.call("web.redirect", "/location")
                errors = []
                user_requests = {}
                create_items = []
                discard_items = []
                transfer_items = []
                money = {}
                item_names = {}
                for ent in req.param("items").split(";"):
                    m = re_request_item.match(ent)
                    if not m:
                        errors.append(self._("Invalid request parameter: %s") % htmlescape(ent))
                        continue
                    dna, price, currency, quantity = m.group(1, 2, 3, 4)
                    price = floatz(price)
                    quantity = intz(quantity)
                    if price > 0 and quantity > 0:
                        if quantity >= 999999:
                            quantity = 999999
                        user_requests[dna] = {
                            "price": price,
                            "currency": currency,
                            "quantity": quantity,
                        }
                now = self.now()
                oplog = self.obj(DBShopOperation)
                oplog.set("performed", now)
                oplog.set("shop", func_id)
                oplog.set("character", character.uuid)
                oplog.set("mode", mode)
                oplog.set("operations", user_requests.copy())
            # processing catalog
            ritems = {}
            for item_type in item_types:
                if req.ok():
                    ureq = user_requests.get(item_type.dna)
                else:
                    ureq = None
                ritem = {
                    "type": item_type.uuid,
                    "dna": item_type.dna,
                    "name": htmlescape(item_type.name),
                    "image": item_type.image("shops"),
                    "description": item_type.get("description"),
                    "quantity": ureq["quantity"] if ureq else 0,
                    "qparam": "q_%s" % item_type.dna,
                    "min_quantity": 0,
                    "max_quantity": max_quantity[item_type.dna] if item_type.dna in max_quantity else 999999,
                    "show_max": item_type.dna in max_quantity,
                    "order": item_type.get("order", 0),
                }
                # item parameters
                params = []
                if mode == "sell":
                    if assortment.get("sell-store-%s" % item_type.uuid):
                        context = "shop-sell"
                    else:
                        context = "shop-sell-new"
                else:
                    context = "shop-buy"
                self.call("item-types.params-owner-important", item_type, params, viewer=character, context=context)
                params = [par for par in params if par.get("value_raw") is not None and not par.get("price") or par.get("important")]
                # item category
                cat = item_type.get("cat-shops")
                misc = None
                found = False
                for c in categories:
                    if c["id"] == cat:
                        found = True
                    elif cat is None and c.get("default"):
                        cat = c["id"]
                        found = True
                    if c.get("misc"):
                        misc = c["id"]
                if not found:
                    cat = misc
                if cat is None:
                    continue
                # item availability
                available = assortment.get("%s-available-%s" % (mode, item_type.uuid), 1)
                if not self.call("script.evaluate-expression", available, globs={"char": character, "item": item_type}, description=lambda: self._("Evaluation of availability of item %s") % item_type.name):
                    continue
                # item price
                price = assortment.get("%s-price-%s" % (mode, item_type.uuid))
                if price is None:
                    price = item_type.get("balance-price")
                    balance_currency = item_type.get("balance-currency")
                    # items without balance price and without shop price are ignored
                    if price is None:
                        continue
                    currency = assortment.get("%s-currency-%s" % (mode, item_type.uuid), balance_currency)
                    if currency != balance_currency:
                        # exchange rate conversion
                        rates = self.call("exchange.rates")
                        if rates is not None:
                            from_rate = rates.get(balance_currency)
                            to_rate = rates.get(currency)
                            if from_rate > 0 and to_rate > 0:
                                price *= from_rate / to_rate;
                else:
                    currency = assortment.get("%s-currency-%s" % (mode, item_type.uuid))
                if price is None:
                    price = 0
                # price correction
                if mode == "sell":
                    description = self._("Sell price evaluation")
                else:
                    description = self._("Buy price evaluation")
                price = self.call("script.evaluate-expression", func.get("shop_%s_price" % mode), globs={"char": character, "price": price, "currency": currency, "item": item_type}, description=description)
                price = floatz(price)
                # rendering price
                price = self.call("money.format-price", price, currency)
                value = self.call("money.price-html", price, currency)
                cinfo = self.call("money.currency-info", currency)
                params.insert(0, {
                    "name": '<span class="item-types-page-price-name">%s</span>' % (self._("Sell price") if mode == "sell" else self._("Buy price")),
                    "value": '<span class="item-types-page-price-value">%s</span>' % value,
                })
                ritem["price"] = price
                ritem["currency"] = currency
                ritem["cicon"] = cinfo.get("icon")
                # storing item
                if params:
                    params[-1]["lst"] = True
                    ritem["params"] = params
                try:
                    ritems[cat].append(ritem)
                except KeyError:
                    ritems[cat] = [ritem]
                # trying to buy
                if req.ok():
                    if ureq:
                        if ureq["price"] != price or ureq["currency"] != currency:
                            errors.append(self._("Price of {item_name_gp} was changed (from {old_price} {old_currency} to {new_price} {new_currency})").format(item_name_gp=htmlescape(item_type.name_gp), old_price=ureq["price"], old_currency=ureq["currency"], new_price=price, new_currency=currency))
                        elif item_type.dna in max_quantity and ureq["quantity"] > max_quantity[item_type.dna]:
                            errors.append(self._("Not enough {item_name_gp}  ({available} pcs available)").format(item_name_gp=htmlescape(item_type.name_gp), available=max_quantity[item_type.dna]))
                        else:
                            # recording money amount
                            try:
                                money[currency] += price * ureq["quantity"]
                            except KeyError:
                                money[currency] = price * ureq["quantity"]
                            # recording money transaction comment
                            try:
                                comments = item_names[currency]
                            except KeyError:
                                comments = {}
                                item_names[currency] = comments
                            try:
                                comments[item_type.name] += ureq["quantity"]
                            except KeyError:
                                comments[item_type.name] = ureq["quantity"]
                            # recording operation
                            if mode == "sell":
                                if assortment.get("sell-store-%s" % item_type.uuid):
                                    transfer_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                                else:
                                    create_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                            else:
                                if assortment.get("buy-store-%s" % item_type.uuid):
                                    transfer_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                                else:
                                    discard_items.append({
                                        "item_type": item_type,
                                        "quantity": ureq["quantity"],
                                    })
                        del user_requests[item_type.dna]
            rcategories = []
            active_cat = req.param("cat")
            any_visible = False
            for cat in categories:
                if cat["id"] in ritems:
                    lst = ritems[cat["id"]]
                    lst.sort(cmp=lambda x, y: cmp(x["order"], y["order"]) or cmp(x["name"], y["name"]))
                    if active_cat:
                        visible = active_cat == cat["id"]
                    else:
                        visible = cat.get("default")
                    rcategories.append({
                        "id": cat["id"],
                        "name_html_js": jsencode(htmlescape(cat["name"])),
                        "visible": visible,
                        "items": lst,
                    })
                    if visible:
                        any_visible = True
            if not any_visible and rcategories:
                rcategories[0]["visible"] = True
            if req.ok():
                if user_requests:
                    errors.append(self._("Shop assortment changed"))
                if mode == "sell":
                    # checking available money
                    if not errors:
                        for currency, amount in money.iteritems():
                            if character.money.available(currency) < amount:
                                errors.append(self.call("money.not-enough-funds", currency))
                redirect = None
                if mode == "buy":
                    if not errors:
                        # transferring items
                        for ent in transfer_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = character.inventory._take_dna(item_type.dna, quantity, "shop-sell", performed=now, reftype=shop_inventory.owtype, ref=shop_inventory.uuid)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from character's inventory (character={character})".format(quantity=quantity, dna=item_type.dna, character=character.uuid))
                            shop_inventory._give(item_type.uuid, quantity, "shop-bought", mod=item_type.mods, performed=now, reftype=character.inventory.owtype, ref=character.inventory.uuid)
                        # discarding items
                        for ent in discard_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = character.inventory._take_dna(item_type.dna, quantity, "shop-sell", performed=now)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from character's inventory (character={character})".format(quantity=quantity, dna=item_type.dna, character=character.uuid))
                else:
                    if not errors:
                        # transferring items
                        for ent in transfer_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            item_type_taken, quantity_taken = shop_inventory._take_dna(item_type.dna, quantity, "shop-sold", performed=now, reftype=character.inventory.owtype, ref=character.inventory.uuid)
                            if quantity_taken is None:
                                raise RuntimeError("Could not take quantity={quantity}, dna={dna} from shop store (shop={shop})".format(quantity=quantity, dna=item_type.dna, shop=shop_inventory.uuid))
                            character.inventory._give(item_type.uuid, quantity, "shop-buy", mod=item_type.mods, performed=now, reftype=shop_inventory.owtype, ref=shop_inventory.uuid)
                        # giving items
                        for ent in create_items:
                            item_type = ent["item_type"]
                            quantity = ent["quantity"]
                            character.inventory._give(item_type.uuid, quantity, "shop-buy", performed=now)
                            # obtaining inventory class
                            if not redirect:
                                # item inventory category
                                cat = item_type.get("cat-inventory")
                                misc = None
                                found = False
                                for c in self.call("item-types.categories", "inventory"):
                                    if c["id"] == cat:
                                        found = True
                                    elif cat is None and c.get("default"):
                                        cat = c["id"]
                                        found = True
                                    if c.get("misc"):
                                        misc = c["id"]
                                if not found:
                                    cat = misc
                                if cat is not None:
                                    redirect = "/inventory?cat=%s#%s" % (cat, item_type.dna)
                # checking overweight conditions
                if mode == "sell":
                    if not errors:
                        errors = character.inventory.constraints_failed()
                # taking of giving money
                if not errors:
                    for currency, amount in money.iteritems():
                        curr_comments = []
                        for item_name, quantity in item_names[currency].iteritems():
                            curr_comments.append({
                                "name": item_name,
                                "quantity": quantity,
                            })
                        curr_comments.sort(cmp=lambda x, y: cmp(x["name"], y["name"]))
                        curr_comments = [ent["name"] if ent["quantity"] == 1 else "%s - %d %s" % (ent["name"], ent["quantity"], self._("pcs")) for ent in curr_comments]
                        comment = ", ".join(curr_comments)
                        if mode == "sell":
                            # debiting character's account
                            if not character.money.debit(amount, currency, "shop-buy", comment=comment, nolock=True, performed=now):
                                errors.append(self._("Technical error during debiting {amount} {currency} (available={available})").format(amount=amount, currency=currency, available=character.money.available(currency)))
                                break
                        else:
                            # crediting character's account
                            character.money.credit(amount, currency, "shop-sell", comment=comment, nolock=True, performed=now)
                            if redirect is None:
                                redirect = "/money/operations/%s" % currency
                if errors:
                    vars["error"] = u"<br />".join(errors)
                else:
                    oplog.store()
                    character.inventory.store()
                    shop_inventory.store()
                    if mode == "sell":
                        self.qevent("shop-bought", char=character)
                    else:
                        self.qevent("shop-sold", char=character)
                    self.call("web.redirect", redirect or "/inventory")
        if rcategories:
            vars["categories"] = rcategories
            vars["Total"] = self._("Total")
            if mode == "sell":
                vars["Submit"] = self._("Buy selected items")
            else:
                vars["Submit"] = self._("Sell selected items")
            vars["pcs"] = self._("pcs")
            content = self.call("game.parse_internal", func.get("shop_template", "shop-items-layout.html"), vars)
            content = self.call("game.parse_internal", "shop-items.html", vars, content)
        elif mode == "sell":
            content = self._("There are no items for sell at the moment")
        else:
            content = self._("You have no items for sell to this shop")
        self.call("game.response_internal", "shop-global.html", vars, content)

    def sell(self, func_id, base_url, func, args, vars):
        return self.transaction("sell", func_id, base_url, func, args, vars)

    def buy(self, func_id, base_url, func, args, vars):
        return self.transaction("buy", func_id, base_url, func, args, vars)

