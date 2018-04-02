from typing import Dict, List

from simfantasy.enum import Attribute, Slot


class Materia:
    """Provides a bonus to a specific stat.

    Arguments:
        attribute (simfantasy.enum.Attribute): The attribute that will be modified.
        bonus (int): Amount of the attribute added.
        name (Optional[str]): Name of the materia, for convenience.

    Attributes:
        attribute (simfantasy.enum.Attribute): The attribute that will be modified.
        bonus (int): Amount of the attribute added.
        name (Optional[str]): Name of the item, for convenience.
    """

    def __init__(self, attribute: Attribute, bonus: int, name: str = None):
        self.attribute: Attribute = attribute
        self.bonus: int = bonus
        self.name: str = name


class Item:
    """A piece of equipment that can be worn.

    Arguments:
        item_level (int): Level of the item.
        slot (simfantasy.enum.Slot): The slot where the item fits.
        stats (Dict[~simfantasy.enums.Attribute, int]): Attributes added by the item.
        melds (Optional[List[Materia]]): Materia affixed to the item.
        name (Optional[str]): Name of the item, for convenience.

    Attributes:
        item_level (int): Level of the item.
        melds (Optional[List[Materia]]): Materia affixed to the item.
        name (Optional[str]): Name of the item, for convenience.
        slot (simfantasy.enum.Slot): The slot where the item fits.
        stats (Dict[~simfantasy.enums.Attribute, int]): Attributes added by the item.
    """

    def __init__(self, item_level: int, slot: Slot, stats: Dict[Attribute, int],
                 melds: List[Materia] = None,
                 name: str = None):
        if melds is None:
            melds = []

        self.item_level = item_level
        self.slot: Slot = slot
        self.stats: Dict[Attribute, int] = stats
        self.melds: List[Materia] = melds
        self.name: str = name


class Weapon(Item):
    """An Item that only fits in :data:`~simfantasy.enums.Slot.SLOT_WEAPON`.

    Arguments:
        item_level (int): Level of the item.
        magic_damage (int): Magic damage inflicted by the weapon. May be hidden for non-casters.
        physical_damage (int): Physical damage inflicted by the weapon. May be hidden for casters.
        delay (float): Weapon attack delay.
        auto_attack (float): Auto attack value.
        stats (Dict[~simfantasy.enums.Attribute, int]): Attributes added by the item.
        melds (Optional[List[Materia]]): Materia affixed to the item.
        name (Optional[str]): Name of the weapon, for convenience.

    Attributes:
        auto_attack (float): Auto attack value.
        delay (float): Weapon attack delay.
        item_level (int): Level of the item.
        magic_damage (int): Magic damage inflicted by the weapon. May be hidden for non-casters.
        melds (Optional[List[Materia]]): Materia affixed to the item.
        name (Optional[str]): Name of the weapon, for convenience.
        physical_damage (int): Physical damage inflicted by the weapon. May be hidden for casters.
        stats (Dict[~simfantasy.enums.Attribute, int]): Attributes added by the item.
    """

    def __init__(self, item_level: int, magic_damage: int, physical_damage: int, delay: float,
                 auto_attack: float,
                 stats: Dict[Attribute, int], melds: List[Materia] = None, name: str = None):
        super().__init__(item_level, Slot.WEAPON, stats, melds, name)

        self.magic_damage: int = magic_damage
        self.physical_damage: int = physical_damage
        self.delay: float = delay
        self.auto_attack: float = auto_attack
