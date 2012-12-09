import mg.constructor
from mg.mmorpg.combats.core import *

class Combats(mg.constructor.ConstructorModule):
    def register(self):
        self.rhook("combats-character.member", self.member)
        self.rhook("combats-character.free", self.free)
        self.rhook("combats-character.busy-lock", self.busy_lock)
        self.rhook("combats-character.set-busy", self.set_busy)
        self.rhook("combats-character.unset-busy", self.unset_busy)

    def member(self, combat, uuid):
        character = self.character(uuid)
        member = CombatCharacterMember(combat, character)
        return member

    def free(self, combat_id, uuid):
        character = self.character(uuid)
        with self.lock([character.busy_lock]):
            busy = character.busy
            if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
                character.unset_busy()

    def busy_lock(self, uuid):
        character = self.character(uuid)
        return character.busy_lock

    def set_busy(self, combat_id, uuid, dry_run=False):
        character = self.character(uuid)
        res = character.set_busy("combat", {
            "priority": 100,
            "show_uri": "/combat/interface/%s" % combat_id,
            "abort_event": "combats-character.abort-busy",
            "combat": combat_id
        }, dry_run)
        if not dry_run and res:
            character.message(self._("You have entered a combat"))
        return not res

    def unset_busy(self, combat_id, uuid):
        character = self.character(uuid)
        busy = character.busy
        if busy and busy["tp"] == "combat" and busy.get("combat") == combat_id:
            character.unset_busy()

class CombatCharacterMember(CombatMember):
    def __init__(self, combat, character, fqn="mg.mmorpg.combats.characters.CombatCharacterMember"):
        CombatMember.__init__(self, combat, fqn)
        self.set_param("char", character)
        self.set_name(character.name)
        self.set_sex(character.sex)
        # get avatar of desired size
        rules = self.combat.rulesinfo
        dim = rules.get("dim_avatar", [120, 220])
        dim = "%dx%d" % (dim[0], dim[1])
        charimage = self.call("charimages.get", character, dim)
        if charimage is None:
            charimage = "/st-mg/constructor/avatars/%s-120x220.jpg" % ("female" if character.sex else "male")
        self.set_param("image", charimage)
