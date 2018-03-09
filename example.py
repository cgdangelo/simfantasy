import logging
from argparse import ArgumentParser
from sys import argv

from simfantasy.enums import Attribute, Race, Slot
from simfantasy.jobs.bard import Bard
from simfantasy.simulator import Actor, Item, Materia, Simulation, Weapon

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--log-event-filter', action='store')
    parser.add_argument('--iterations', action='store', type=int, default=100)
    parser.add_argument('--log-action-attempts', action='store_true', default=False, dest='log_action_attempts')

    heap_options = parser.add_mutually_exclusive_group()
    heap_options.add_argument('--log-pushes', action='store_false', default=True, dest='log_pops')
    heap_options.add_argument('--log-pops', action='store_false', default=True, dest='log_pushes')

    args = parser.parse_args(argv[1:])

    sim = Simulation(log_level=logging.DEBUG if args.debug else None,
                     log_event_filter=args.log_event_filter,
                     log_pushes=args.log_pushes,
                     log_pops=args.log_pops,
                     iterations=args.iterations,
                     log_action_attempts=args.log_action_attempts)

    enemy = Actor(sim=sim, race=Race.ENEMY)

    savage_aim_vi = Materia(Attribute.CRITICAL_HIT, 40)
    savage_might_vi = Materia(Attribute.DETERMINATION, 40)
    heavens_eye_vi = Materia(Attribute.DIRECT_HIT, 40)
    vitality_vi = Materia(Attribute.VITALITY, 25)

    kujakuo_kai = Weapon(item_level=370, name='Kujakuo Kai', physical_damage=104, magic_damage=70, auto_attack=105.38,
                         delay=3.04,
                         stats={
                             Attribute.DEXTERITY: 347,
                             Attribute.VITALITY: 380,
                             Attribute.CRITICAL_HIT: 218,
                             Attribute.DIRECT_HIT: 311,
                         },
                         melds=[savage_aim_vi, savage_aim_vi])

    true_linen_cap_of_aiming = Item(item_level=350, name='True Linen Cap of Aiming', slot=Slot.HEAD,
                                    stats={
                                        Attribute.DEXTERITY: 180,
                                        Attribute.VITALITY: 193,
                                        Attribute.CRITICAL_HIT: 114,
                                        Attribute.DIRECT_HIT: 163,
                                        Attribute.DEFENSE: 428,
                                        Attribute.MAGIC_DEFENSE: 428,
                                    },
                                    melds=[savage_aim_vi, savage_might_vi])

    true_linen_jacket_of_aiming = Item(item_level=350, name='True Linen Jacket of Aiming', slot=Slot.BODY,
                                       stats={
                                           Attribute.DEXTERITY: 293,
                                           Attribute.VITALITY: 314,
                                           Attribute.CRITICAL_HIT: 265,
                                           Attribute.DETERMINATION: 186,
                                           Attribute.DEFENSE: 599,
                                           Attribute.MAGIC_DEFENSE: 599,
                                       },
                                       melds=[heavens_eye_vi, heavens_eye_vi])

    diamond_gauntlets_of_aiming = Item(item_level=370, name='Diamond Gauntlets of Aiming', slot=Slot.HANDS,
                                       stats={
                                           Attribute.DEXTERITY: 198,
                                           Attribute.VITALITY: 217,
                                           Attribute.SKILL_SPEED: 178,
                                           Attribute.DIRECT_HIT: 125,
                                           Attribute.DEFENSE: 448,
                                           Attribute.MAGIC_DEFENSE: 448,
                                       },
                                       melds=[savage_aim_vi, savage_aim_vi])

    slothskin_belt_of_aiming = Item(item_level=350, name='Slothskin Belt of Aiming', slot=Slot.WAIST,
                                    stats={
                                        Attribute.DEXTERITY: 135,
                                        Attribute.VITALITY: 145,
                                        Attribute.DETERMINATION: 122,
                                        Attribute.DIRECT_HIT: 86,
                                        Attribute.DEFENSE: 371,
                                        Attribute.MAGIC_DEFENSE: 371,
                                    },
                                    melds=[savage_aim_vi])

    diamond_trousers_of_aiming = Item(item_level=370, name='Diamond Trousers of Aiming', slot=Slot.LEGS,
                                      stats={
                                          Attribute.DEXTERITY: 322,
                                          Attribute.VITALITY: 353,
                                          Attribute.DETERMINATION: 289,
                                          Attribute.SKILL_SPEED: 202,
                                          Attribute.DEFENSE: 627,
                                          Attribute.MAGIC_DEFENSE: 627,
                                      },
                                      melds=[savage_aim_vi, savage_aim_vi])

    slothskin_boots_of_aiming = Item(item_level=350, name='Slothskin Boots of Aiming', slot=Slot.FEET,
                                     stats={
                                         Attribute.DEXTERITY: 180,
                                         Attribute.VITALITY: 193,
                                         Attribute.CRITICAL_HIT: 114,
                                         Attribute.SKILL_SPEED: 163,
                                         Attribute.DEFENSE: 428,
                                         Attribute.MAGIC_DEFENSE: 428,
                                     },
                                     melds=[savage_aim_vi, heavens_eye_vi])

    diamond_earring_of_aiming = Item(item_level=370, name='Diamond Earring of Aiming', slot=Slot.EARRINGS,
                                     stats={
                                         Attribute.DEXTERITY: 149,
                                         Attribute.CRITICAL_HIT: 93,
                                         Attribute.DETERMINATION: 133,
                                         Attribute.DEFENSE: 1,
                                         Attribute.MAGIC_DEFENSE: 1,
                                     },
                                     melds=[savage_aim_vi])

    diamond_necklace_of_aiming = Item(item_level=370, name='Diamond Necklace of Aiming', slot=Slot.NECKLACE,
                                      stats={
                                          Attribute.DEXTERITY: 149,
                                          Attribute.CRITICAL_HIT: 93,
                                          Attribute.DETERMINATION: 133,
                                          Attribute.DEFENSE: 1,
                                          Attribute.MAGIC_DEFENSE: 1,
                                      },
                                      melds=[vitality_vi])

    ryumyaku_bracelet_of_aiming = Item(item_level=360, name='Ryumyaku Bracelet of Aiming', slot=Slot.BRACELET,
                                       stats={
                                           Attribute.DEXTERITY: 142,
                                           Attribute.DETERMINATION: 128,
                                           Attribute.DIRECT_HIT: 90,
                                           Attribute.DEFENSE: 1,
                                           Attribute.MAGIC_DEFENSE: 1,
                                       },
                                       melds=[savage_aim_vi])

    diamond_ring_of_aiming = Item(item_level=370, name='Diamond Ring of Aiming', slot=Slot.RING,
                                  stats={
                                      Attribute.DEXTERITY: 149,
                                      Attribute.DETERMINATION: 93,
                                      Attribute.DIRECT_HIT: 133,
                                      Attribute.DEFENSE: 1,
                                      Attribute.MAGIC_DEFENSE: 1,
                                  },
                                  melds=[vitality_vi])

    carborundum_ring_of_aiming = Item(item_level=350, name='Carborundum Ring of Aiming', slot=Slot.RING,
                                      stats={
                                          Attribute.DEXTERITY: 135,
                                          Attribute.CRITICAL_HIT: 86,
                                          Attribute.DIRECT_HIT: 122,
                                          Attribute.DEFENSE: 1,
                                          Attribute.MAGIC_DEFENSE: 1,
                                      },
                                      melds=[vitality_vi])

    bard = Bard(sim, race=Race.HIGHLANDER, name='Dikembe', target=enemy,
                gear={
                    Slot.WEAPON: kujakuo_kai,
                    Slot.HEAD: true_linen_cap_of_aiming,
                    Slot.BODY: true_linen_jacket_of_aiming,
                    Slot.HANDS: diamond_gauntlets_of_aiming,
                    Slot.WAIST: slothskin_belt_of_aiming,
                    Slot.LEGS: diamond_trousers_of_aiming,
                    Slot.FEET: slothskin_boots_of_aiming,
                    Slot.EARRINGS: diamond_earring_of_aiming,
                    Slot.NECKLACE: diamond_necklace_of_aiming,
                    Slot.BRACELET: ryumyaku_bracelet_of_aiming,
                    Slot.LEFT_RING: diamond_ring_of_aiming,
                    Slot.RIGHT_RING: carborundum_ring_of_aiming
                })

    sim.run()
