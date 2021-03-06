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
from mg.mmorpg.locations_classes import *
from mg.core.safejson import SafeEncoder
import re
import time

re_valid_identifier = re.compile(r'^u_[a-z_][a-z0-9_]*$', re.IGNORECASE)
re_objects_arg = re.compile(r'^([0-9a-f]+)(?:|/(.+))$')
re_del = re.compile(r'del/(.+)')
re_action = re.compile(r'^(u_[a-z_][a-z0-9_]*)/action/([a-z0-9_]+)(?:|/(.+))$', re.IGNORECASE)
re_polygon_param = re.compile(r'^polygon-(\d+)$')

class LocationObjectsAdmin(ConstructorModule):
    def register(self):
        self.rhook("permissions.list", self.permissions_list)
        self.rhook("ext-admin-locations.objects", self.admin_objects, priv="locations.objects")
        self.rhook("headmenu-admin-locations.objects", self.headmenu_objects)
        self.rhook("admin-locations.links", self.links)
        self.rhook("admin-locations.valid-transitions", self.valid_transitions)
        self.rhook("admin-storage.group-names", self.group_names)
        self.rhook("advice-admin-locations.index", self.advice_locations)

    def advice_locations(self, hook, args, advice):
        advice.append({"title": self._("Location objects documentation"), "content": self._('You can find detailed information on the location objects system in the <a href="//www.%s/doc/location-objects" target="_blank">locations objects documentation page</a> in the reference manual.') % self.main_host, "order": 10})

    def group_names(self, group_names):
        group_names["location-objects"] = self._("Location objects")

    def links(self, location, links):
        req = self.req()
        if req.has_access("locations.objects"):
            if location.image_type == "canvas":
                links.append({"hook": "locations/objects/%s" % location.uuid, "text": self._("Objects"), "order": 30})
        
    def permissions_list(self, perms):
        perms.append({"id": "locations.objects", "name": self._("Locations objects")})

    def headmenu_objects(self, args):
        return [self._("Objects"), "locations/editor/%s" % htmlescape(args)]

    def admin_objects(self):
        req = self.req()
        location = self.location(req.args)
        if not location.valid():
            self.call("admin.redirect", "locations/editor")
        if location.image_type == "canvas":
            image = location.db_location.get("image_static")
            width = location.db_location.get("image_static_w")
            height = location.db_location.get("image_static_h")
        else:
            self.call("admin.response", self._("This type of location visualization is not supported by location objects subsystem"), {})
        # Save
        if req.ok():
            errors = {}
            objects = {}
            for key in req.param_dict().keys():
                m = re_polygon_param.match(key)
                if m:
                    obj_id = int(m.group(1))
                    obj = {}
                    objects[obj_id] = obj
                    # identifier
                    ident = req.param("id-%d" % obj_id).strip()
                    if ident != "":
                        if not re_valid_identifier.match(ident):
                            errors["id-%d" % obj_id] = self._("Object identifier must start with 'u_' and contain latin letters, digits and underscores only")
                        else:
                            obj["id"] = ident
                    # order
                    obj["order"] = intz(req.param("order-%d" % obj_id))
                    # coordinates
                    x = req.param("x-%d" % obj_id)
                    if not valid_int(x):
                        errors["x-%d" % obj_id] = self._("Value must be integer")
                    else:
                        obj["x"] = intz(x)
                    y = req.param("y-%d" % obj_id)
                    if not valid_int(y):
                        errors["y-%d" % obj_id] = self._("Value must be integer")
                    else:
                        obj["y"] = intz(y)
                    # dimensions
                    width = req.param("width-%d" % obj_id)
                    if not valid_int(width):
                        errors["error"] = self._("Invalid image width")
                    else:
                        obj["width"] = intz(width)
                    height = req.param("height-%d" % obj_id)
                    if not valid_int(height):
                        errors["error"] = self._("Invalid image height")
                    else:
                        obj["height"] = intz(height)
                    # position
                    if req.param("position-expr-%d" % obj_id):
                        position = req.param("position-%d" % obj_id)
                        char = self.character(req.user())
                        obj["position"] = self.call("script.admin-expression", "position-%d" % obj_id, errors, globs={"char": char, "loc": char.location, "t": self.time()})
                    # visible
                    visible = req.param("visible-%d" % obj_id)
                    if visible:
                        char = self.character(req.user())
                        obj["visible"] = self.call("script.admin-expression", "visible-%d" % obj_id, errors, globs={"char": char, "loc": char.location})
                    # image
                    image = req.param("image-%d" % obj_id)
                    if image:
                        if not image.startswith("//"):
                            errors["errormsg"] = self._("Image URIs must belong to the storage")
                        obj["image"] = image
                    # polygon data
                    obj["polygon"] = req.param("polygon-%d" % obj_id)
                    poly = obj["polygon"].split(",")
                    if len(poly) == 0:
                        errors["polygon-%d" % obj_id] = self._("Polygon may not be empty")
                    elif len(poly) % 2:
                        errors["polygon-%d" % obj_id] = self._("Odd number of coordinates")
                    elif len(poly) < 6:
                        errors["polygon-%d" % obj_id] = self._("Minimal number of points is 3")
                    else:
                        for coo in poly:
                            if not valid_int(coo):
                                errors["polygon-%d" % obj_id] = self._("Invalid non-integer coordinate encountered")
                                break
                    # action
                    action = req.param("v_action-%d" % obj_id)
                    obj["action"] = action
                    if action == "move":
                        loc = req.param("v_location-%d" % obj_id)
                        if not loc:
                            errors["location-%d" % obj_id] = self._("Location not specified")
                        else:
                            loc_obj = self.location(loc)
                            if not loc_obj.valid():
                                errors["location-%d" % obj_id] = self._("Invalid location specified")
                            elif loc_obj.uuid == location.uuid:
                                errors["location-%d" % obj_id] = self._("Link to the same location")
                            else:
                                obj["loc"] = loc
                    elif action == "open":
                        url = req.param("url-%d" % obj_id)
                        if not url:
                            errors["url-%d" % obj_id] = self._("This field is mandatory")
                        elif not url.startswith("/"):
                            errors["url-%d" % obj_id] = self._("URL must start with '/'")
                        else:
                            obj["url"] = url
                    elif not self.call("admin-locations.map-zone-action-%s" % action, obj_id, obj, errors):
                        if "action" in obj:
                            del obj["action"]
                    # hint
                    hint = req.param("hint-%d" % obj_id)
                    obj["hint"] = hint
            if errors:
                self.call("web.response_json", errors)
            objlist = objects.values()
            objlist.sort(cmp=lambda x, y: cmp(x["order"], y["order"]))
            location.db_location.set("static_objects", objlist)
            self.call("admin-locations.update-transitions", location.db_location)
            location.db_location.store()
            self.call("web.response_json", {"success": True, "redirect": "locations/objects/%s" % location.uuid, "parameters": {"saved": 1}})
        # Load locations
        locations = []
        lst = self.objlist(DBLocationList, query_index="all")
        lst.load()
        for db_loc in lst:
            if db_loc.uuid != location.uuid:
                locations.append({
                    "id": db_loc.uuid,
                    "name": jsencode(db_loc.get("name"))
                })
        actions = [("none", self._("No action")), ("move", self._("Move to another location")), ("open", self._("Open URL"))]
        self.call("admin-locations.map-zone-actions", location, actions)
        links = []
        self.call("admin-locations.render-links", location, links)
        # Load objects
        static_objects = location.db_location.get("static_objects", [])
        objects = []
        for obj in static_objects:
            robj = {
                "image": jsencode(obj.get("image")),
                "id": obj.get("id", ""),
                "x": obj.get("x"),
                "y": obj.get("y"),
                "width": obj.get("width"),
                "height": obj.get("height"),
                "polygon": jsencode(obj.get("polygon")),
                "action": jsencode(obj.get("action", "none")),
                "loc": jsencode(obj.get("loc")),
                "url": jsencode(obj.get("url")),
                "hint": jsencode(obj.get("hint")),
                "visible": jsencode(self.call("script.unparse-expression", obj.get("visible", 1))),
                "position": jsencode(self.call("script.unparse-expression", obj.get("position"))) if "position" in obj else "",
            }
            self.call("admin-locations.map-zone-%s-render" % robj["action"], obj, robj)
            objects.append(robj)
        vars = {
            "image": image,
            "width": width,
            "height": height,
            "ie_warning": self._("Warning! Internet Explorer browser is not supported. Location editor may work slowly and unstable. Mozilla Firefox, Google Chrome and Opera are fully supported"),
            "submit_url": "/%s/%s/%s" % (req.group, req.hook, req.args),
            "locations": locations,
            "actions": actions,
            "links": links,
            "objects": objects,
        }
        if not self.conf("module.storage"):
            vars["storage_unavailable"] = jsencode(self._("To access this function you need to enable 'Static Storage' system module"))
        elif not req.has_access("storage.static"):
            vars["storage_unavailable"] = jsencode(self._("You don't have permission to upload objects to the static storage"))
        if req.param("saved"):
            vars["saved"] = {"text": self._("Location saved successfully")}
        self.call("admin-locations.render-imagemap-editor", location, vars)
        self.call("admin.response_template", "admin/locations/objects.html", vars)

    def valid_transitions(self, db_loc, valid_transitions):
        if db_loc.get("image_type") == "canvas":
            if db_loc.get("static_objects"):
                for obj in db_loc.get("static_objects"):
                    if obj.get("action") == "move" and obj.get("loc"):
                        valid_transitions.add(obj.get("loc"))

class LocationObjects(ConstructorModule):
    def register(self):
        self.rhook("location.render", self.location_render)

    def child_modules(self):
        return [
            "mg.mmorpg.locations.LocationsCanvas", "mg.mmorpg.locations.LocationsCanvasAdmin",
            "mg.mmorpg.locobjects.LocationObjectsAdmin", "mg.core.timesync.TimeSync",
        ]

    def location_render(self, character, location, vars):
        if location.image_type == "canvas":
            loc_init = vars.get("loc_init", [])
            vars["loc_init"] = loc_init
            loc_init.append("LocObjects.init();");
            loc_init.append("LocObjects.setBackgroundImage('%s');" % location.db_location.get("image_static"))
            db_loc = location.db_location
            if db_loc.get("static_objects"):
                ident = 0
                order = 0
                for obj in db_loc.get("static_objects"):
                    ident += 1
                    order += 1
                    rclick = {}
                    if obj.get("action"):
                        rclick["action"] = obj["action"]
                    if obj.get("loc"):
                        rclick["loc"] = obj["loc"]
                    if obj.get("ev"):
                        rclick["ev"] = obj["ev"]
                    if obj.get("globfunc"):
                        rclick["globfunc"] = obj["globfunc"]
                    if obj.get("specfunc"):
                        rclick["specfunc"] = obj["specfunc"]
                    if obj.get("url"):
                        rclick["url"] = obj["url"]
                    robj = {
                        "id": obj.get("id") or ("auto_%s" % ident),
                        "width": obj["width"],
                        "height": obj["height"],
                        "image": obj.get("image"),
                        "polygon": obj["polygon"],
                        "hint": obj["hint"],
                        "click": rclick
                    }
                    globs = {"char": character, "loc": location}
                    keep_globs = {"t": True}
                    robj["visible"] = self.call("script.evaluate-expression", obj.get("visible"), globs=globs, keep_globs=keep_globs)
                    if "position" in obj:
                        robj["position"] = self.call("script.evaluate-expression", obj.get("position"), globs=globs, keep_globs=keep_globs)
                    else:
                        robj["position"] = ["call", "vec3", obj["x"], order, obj["y"]]
                    loc_init.append("LocObjects.addStaticObject(%s);" % json.dumps(robj, cls=SafeEncoder))
            loc_init.append("LocObjects.run();");
