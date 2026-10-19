# Dependency audit for player customization

Inventory: 136 pinned mods, 306 top-level/nested Fabric metadata records. Recomputed from previously recorded Fabric metadata for unchanged pinned identities; no fresh JAR downloads or hash verification in this run. No installed instance was launched or modified.

Reproduce with Python 3.11+: `python scripts/audit_customization.py --jars PATH_TO_PINNED_JARS`. The input directory is read only. The output JSON records hashes, exact versions, environment, dependency ranges, aliases, nested origins, breaks/conflicts, and dependency providers for every mod.

`depends` is mandatory; `breaks` is a hard incompatibility; `conflicts` is a Fabric warning. `recommends`/`suggests` are recorded as advisory. Shared libraries remain required when making their users independent options. Packwiz `side` alone does not establish dependency safety.

Dependency provider lists are alternatives: Fabric API modules can be supplied by Fabric API itself or by another mod's bundled JAR. A listed provider is not individually mandatory when another compatible provider remains. The JSON also includes each root's transitive possible provider closure; it deliberately preserves these alternatives.

## Client-only decisions

| Component | Fabric ID | Decision | Required users if removed |
|---|---|---|---|
| AmbientSounds 6 | `ambientsounds` | optional-default-on | None |
| Axolotl Buckets | `axolotlbuckets` | optional-default-on | None |
| Chat Heads | `chat_heads` | optional-default-on | None |
| Chat Animation [Smooth Chat] | `chatanimation` | optional-default-on | None |
| Continuity | `continuity` | optional-default-on | None |
| Cool Rain | `coolrain` | optional-default-on | None |
| [EMF] Entity Model Features [Fabric & Forge] | `entity_model_features` | optional-default-on | None |
| [ETF] Entity Texture Features - [Fabric & Forge] | `entity_texture_features` | required-support | entity_model_features → entity_texture_features |
| Entity Culling | `entityculling` | optional-default-on | None |
| Glowing Trims Mod | `glowing_trims` | optional-default-on | None |
| ImmediatelyFast | `immediatelyfast` | optional-default-on | None |
| Inventory Profiles Next | `inventoryprofilesnext` | optional-default-on | None |
| Iris Shaders | `iris` | optional-default-on | None |
| Legendary Tooltips [Fabric] | `legendarytooltips` | optional-default-on | None |
| libIPN | `libipn` | required-support | inventoryprofilesnext → libipn |
| Lighty | `lighty` | optional-default-on | None |
| Mod Menu | `modmenu` | optional-default-on | None |
| Natural Waters | `naturalwaters` | optional-default-on | None |
| Particle Effects | `particle_effects` | optional-default-on | None |
| Particular ✨ Reforged | `particular` | optional-default-on | None |
| Presence Footsteps | `presencefootsteps` | optional-default-on | None |
| Prism [Fabric] | `prism` | required-support | legendarytooltips → prism |
| Scale Me | `scaleme` | optional-default-on | None |
| Sodium | `sodium` | required-support | iris → sodium |
| Status Effect Bars | `status-effect-bars` | optional-default-on | None |
| Studious Keybinds | `studiouskeybinds` | optional-default-on | None |
| Swinging Lanterns | `swinginglanterns` | optional-default-on | None |
| Zoomify | `zoomify` | optional-default-on | None |

## Selection validation

24 independent client options represent 16,777,216 selections. Each option plus the mandatory set is checked, and the full set is checked for incompatibilities. This proves availability of positive mandatory dependencies under all unions of options; it is not a complete Fabric version resolver, client launch, rendering, or server join test.

All static mandatory-dependency and declared incompatibility checks pass.

## Complete inventory

| Packwiz file | Fabric ID / version | Side | Available dependency provider owners (including nested metadata) |
|---|---|---|---|
| `mods/3d-maps.pw.toml` | `maps3d` / `0.8.2` | both | fabric-api |
| `mods/additional-lanterns.pw.toml` | `additionallanterns` / `1.1.2` | both | fabric-api, supermartijn642s-core-lib |
| `mods/ambientsounds.pw.toml` | `ambientsounds` / `6.3.10` | client | creativecore, fabric-api |
| `mods/appleskin.pw.toml` | `appleskin` / `3.0.10+mc26.3` | both | fabric-api |
| `mods/archers.pw.toml` | `archers` / `3.1.4+26.3` | both | armor-model-api, bundle-api, fabric-api, ranged-weapon-api, rune-crafting, spell-engine, structure-pool-api |
| `mods/architectury-api.pw.toml` | `architectury` / `22.0.5` | both | fabric-api |
| `mods/armor-model-api.pw.toml` | `armor_model_api` / `1.1.2+26.3` | both | fabric-api, modmenu, simple-voice-chat, sodium |
| `mods/armory-rpg-series.pw.toml` | `armory_rpgs` / `1.5.3+26.3` | both | armor-model-api, fabric-api, ranged-weapon-api, spell-engine |
| `mods/arsenal-rpg-series.pw.toml` | `arsenal` / `1.5.1+26.3` | both | fabric-api, ranged-weapon-api, spell-engine |
| `mods/axolotl-buckets.pw.toml` | `axolotlbuckets` / `2.0.0+26.3` | client | fabric-api |
| `mods/baguettelib.pw.toml` | `baguettelib` / `2.0.7` | both | fabric-api |
| `mods/balm.pw.toml` | `balm` / `26.3.0.3` | both | fabric-api |
| `mods/beautify-refabricated.pw.toml` | `beautify` / `3.0.0+26.3` | both | cloth-config, fabric-api |
| `mods/better-combat-by-daedelus.pw.toml` | `bettercombat` / `3.2.2` | both | cloth-config, fabric-api, player-animation-library |
| `mods/bundle-api.pw.toml` | `bundleapi` / `5.0.0+26.3` | both | Builtins / bundled only |
| `mods/chat-heads.pw.toml` | `chat_heads` / `1.3.2` | client | Builtins / bundled only |
| `mods/chatanimation.pw.toml` | `chatanimation` / `1.3.4` | client | Builtins / bundled only |
| `mods/chunky-pregenerator.pw.toml` | `chunky` / `1.5.3` | both | fabric-api |
| `mods/climate-rivers.pw.toml` | `climaterivers` / `26.3.1` | both | fabric-api, forge-config-api-port, lithostitched, puzzles-lib |
| `mods/cloth-config.pw.toml` | `cloth-config` / `26.3.159` | both | Builtins / bundled only |
| `mods/collective.pw.toml` | `collective` / `8.47` | both | fabric-api |
| `mods/colonial-delight.pw.toml` | `colonialdelight` / `1.0.2` | both | fabric-api, farmers-delight-refabricated |
| `mods/colorful-trims.pw.toml` | `mr_colorful_trims` / `2.0` | both | fabric-api, sodium |
| `mods/continuity.pw.toml` | `continuity` / `3.0.1+26.3` | client | fabric-api |
| `mods/coolrain.pw.toml` | `coolrain` / `unspecified` | client | fabric-api, sodium |
| `mods/crate-delight-fabric.pw.toml` | `cratedelight` / `26.09.15-26.3-fabric` | both | fabric-api |
| `mods/creativecore.pw.toml` | `creativecore` / `2.14.19` | both | fabric-api |
| `mods/critical-strike.pw.toml` | `critical_strike` / `1.0.6+26.3` | both | fabric-api |
| `mods/decubed-dungeons.pw.toml` | `mr_dungeons` / `1.13.1` | both | fabric-api, sodium |
| `mods/delight-lib.pw.toml` | `delightlib` / `26.09.16-26.3-fabric` | both | fabric-api, farmers-delight-refabricated |
| `mods/dungeon-and-taverns.pw.toml` | `mr_dungeons_andtaverns` / `6.0.2` | both | fabric-api, sodium |
| `mods/easy-npc-config-ui.pw.toml` | `easy_npc_config_ui` / `7.15.0` | both | easy-npc-core, fabric-api |
| `mods/easy-npc-core.pw.toml` | `easy_npc` / `7.15.0` | both | fabric-api |
| `mods/entity-model-features.pw.toml` | `entity_model_features` / `3.3.11` | client | entity-texture-features-fabric |
| `mods/entity-texture-features-fabric.pw.toml` | `entity_texture_features` / `7.2.5` | client | Builtins / bundled only |
| `mods/entityculling.pw.toml` | `entityculling` / `1.11.3` | client | fabric-api |
| `mods/fabric-api.pw.toml` | `fabric-api` / `0.163.0+26.3` | both | irisshaders, modmenu, simple-voice-chat, sodium |
| `mods/fabric-language-kotlin.pw.toml` | `fabric-language-kotlin` / `1.14.2+kotlin.2.4.21` | both | Builtins / bundled only |
| `mods/falling-tree.pw.toml` | `fallingtree` / `25` | both | fabric-api, modmenu, simple-voice-chat, sodium |
| `mods/farmers-delight-refabricated.pw.toml` | `farmersdelight` / `26.3-3.6.28+refabricated` | both | fabric-api |
| `mods/ferritecore-fabric.pw.toml` | `ferritecore` / `9.0.0` | both | Builtins / bundled only |
| `mods/forge-config-api-port.pw.toml` | `forgeconfigapiport` / `26.3.1` | both | fabric-api |
| `mods/frog-petting.pw.toml` | `frog_petting` / `5.1+26.3` | both | cloth-config, fabric-api |
| `mods/frozenlib.pw.toml` | `frozenlib` / `3.0.3` | both | fabric-api |
| `mods/gazebos.pw.toml` | `gazebo` / `2.2.1+26.3` | both | fabric-api, spell-engine, structure-pool-api |
| `mods/geckolib.pw.toml` | `geckolib` / `5.5.7` | both | fabric-api |
| `mods/glitchcore.pw.toml` | `glitchcore` / `26.3.0.0.5` | both | fabric-api |
| `mods/glowing-trims-mod.pw.toml` | `glowing_trims` / `1.0.26.3.x` | client | fabric-api |
| `mods/iceberg-fabric.pw.toml` | `iceberg` / `1.4.3.1` | both | fabric-api |
| `mods/icys-better-horses.pw.toml` | `icys-better-horses` / `2.1.2` | both | fabric-api, geckolib, modonomicon |
| `mods/immediatelyfast.pw.toml` | `immediatelyfast` / `1.17.1+26.3` | client | Builtins / bundled only |
| `mods/inventory-profiles-next.pw.toml` | `inventoryprofilesnext` / `2.3.8` | client | fabric-language-kotlin, libipn |
| `mods/irisshaders.pw.toml` | `iris` / `1.11.7+mc26.3` | client | sodium |
| `mods/jei.pw.toml` | `jei` / `31.15.0.79` | both | fabric-api, mezzconfig |
| `mods/jewelry.pw.toml` | `jewelry` / `2.5.1+26.3` | both | fabric-api, ranged-weapon-api, spell-power, structure-pool-api |
| `mods/kaleidoscope-tavern-refabricated.pw.toml` | `kaleidoscope_tavern` / `1.2.0.11-fabric+mc26.3` | both | fabric-api |
| `mods/key.pw.toml` | `mr_key` / `8.1` | both | fabric-api, sodium |
| `mods/khazodacore.pw.toml` | `khazodacore` / `1.0.4+26.3` | both | fabric-api |
| `mods/legendary-tooltips-fabric.pw.toml` | `legendarytooltips` / `1.6.3` | client | fabric-api, iceberg-fabric, prism-fabric |
| `mods/libipn.pw.toml` | `libipn` / `6.9.0` | client | fabric-language-kotlin |
| `mods/lighty.pw.toml` | `lighty` / `4.0.1` | client | fabric-api |
| `mods/lithium.pw.toml` | `lithium` / `0.26.2+mc26.3` | both | Builtins / bundled only |
| `mods/lithostitched.pw.toml` | `lithostitched` / `2.0.5` | both | Builtins / bundled only |
| `mods/lost-relics.pw.toml` | `lost_relics` / `26.3-r1` | both | fabric-api, strawberrylib, trinkets-updated |
| `mods/ly-graves.pw.toml` | `mr_ly_graves` / `3.0.1` | both | fabric-api, sodium |
| `mods/macaws-lights-and-lamps.pw.toml` | `mcwlights` / `1.1.5` | both | fabric-api |
| `mods/mezzconfig.pw.toml` | `mezz_config` / `0.6.8` | both | fabric-api |
| `mods/modmenu.pw.toml` | `modmenu` / `21.0.0` | client | fabric-api, irisshaders, simple-voice-chat, sodium |
| `mods/modonomicon.pw.toml` | `modonomicon` / `2.16.0` | both | fabric-api |
| `mods/more-armor-trims.pw.toml` | `more_armor_trims` / `1.5.4-26.3` | both | fabric-api |
| `mods/more-delight-fabric.pw.toml` | `moredelight` / `26.09.16-26.3-fabric` | both | delight-lib, fabric-api, farmers-delight-refabricated |
| `mods/natural-waters.pw.toml` | `naturalwaters` / `26.3.0` | client | fabric-api, forge-config-api-port, puzzles-lib |
| `mods/naturalist.pw.toml` | `naturalist` / `2.0.6` | both | fabric-api |
| `mods/nemos-woodcutter.pw.toml` | `nemos_woodcutter` / `26.3-1.15.2` | both | fabric-api |
| `mods/netherportalfix.pw.toml` | `netherportalfix` / `26.3.0.1` | both | balm, fabric-api |
| `mods/open-parties-and-claims.pw.toml` | `openpartiesandclaims` / `0.32.8` | both | fabric-api, forge-config-api-port |
| `mods/paladins-and-priests.pw.toml` | `paladins` / `3.1.4+26.3` | both | armor-model-api, fabric-api, rune-crafting, spell-engine, spell-power, structure-pool-api |
| `mods/particle-effects.pw.toml` | `particle_effects` / `1.6.0+26.3+fabric` | client | fabric-api |
| `mods/particular-reforged.pw.toml` | `particular` / `1.5.7` | client | baguettelib, fabric-api, forge-config-api-port |
| `mods/placeholder-api.pw.toml` | `placeholder-api` / `3.2.0+26.3` | both | Builtins / bundled only |
| `mods/player-animation-library.pw.toml` | `player_animation_library` / `1.2.8+mc.26.3` | both | fabric-api, modmenu, simple-voice-chat, sodium |
| `mods/plushables.pw.toml` | `plushables` / `2.6.1+26.3` | both | fabric-api, khazodacore |
| `mods/polydex.pw.toml` | `polydex` / `1.11.0+26.3-rc-1` | both | fabric-api, modmenu, polymer, simple-voice-chat, sodium |
| `mods/polymer.pw.toml` | `polymer-bundled` / `0.18.2+26.3` | both | Builtins / bundled only |
| `mods/presence-footsteps.pw.toml` | `presencefootsteps` / `1.14.0+26.3` | client | fabric-api |
| `mods/prism-fabric.pw.toml` | `prism` / `1.1.3` | client | fabric-api |
| `mods/puddles-floods.pw.toml` | `puddleflood` / `1.1.6` | both | fabric-api |
| `mods/puffish-attributes.pw.toml` | `puffish_attributes` / `0.8.3` | both | fabric-api |
| `mods/puffish-skills.pw.toml` | `puffish_skills` / `0.19.2` | both | fabric-api |
| `mods/puzzles-lib.pw.toml` | `puzzleslib` / `26.3.13` | both | fabric-api, forge-config-api-port |
| `mods/pyrite.pw.toml` | `pyrite` / `0.18.3+26.3` | both | fabric-api |
| `mods/ranged-weapon-api.pw.toml` | `ranged_weapon_api` / `4.0.0+26.3` | both | fabric-api |
| `mods/relics-rpg.pw.toml` | `relics_rpgs` / `1.4.1+26.3` | both | fabric-api, ranged-weapon-api, spell-engine |
| `mods/ribbits-updated.pw.toml` | `ribbits` / `4.2.0` | both | fabric-api, geckolib |
| `mods/rogues-and-warriors.pw.toml` | `rogues` / `3.1.4+26.3` | both | armor-model-api, fabric-api, spell-engine, structure-pool-api |
| `mods/rune-crafting.pw.toml` | `runes` / `1.3.2+26.3` | both | fabric-api |
| `mods/rustic-delight.pw.toml` | `rusticdelight` / `1.7.0` | both | cloth-config, fabric-api, farmers-delight-refabricated |
| `mods/scale-me.pw.toml` | `scaleme` / `3.3.2` | client | coolrain, fabric-api, sodium, ubes-delight |
| `mods/serene-seasons.pw.toml` | `sereneseasons` / `26.1.2.0.7` | both | fabric-api, glitchcore |
| `mods/shogi.pw.toml` | `shogi` / `26.3.0.3` | both | fabric-api |
| `mods/simple-voice-chat.pw.toml` | `voicechat` / `2.6.24+26.3` | both | fabric-api, irisshaders, modmenu, sodium |
| `mods/skill-tree.pw.toml` | `skill_tree_rpgs` / `1.6.2+26.3` | both | fabric-api, puffish-skills, spell-engine, spell-power |
| `mods/skniros-furniture.pw.toml` | `skniro_furniture` / `1.6.1-26.3-Fabric` | both | fabric-api |
| `mods/sodium.pw.toml` | `sodium` / `0.9.3-beta.1+mc26.3` | client | fabric-api, irisshaders, modmenu, simple-voice-chat |
| `mods/sound-physics-remastered.pw.toml` | `sound_physics_remastered` / `1.5.1+26.3` | both | Builtins / bundled only |
| `mods/spanish-delight-refabricated.pw.toml` | `spanishdelight` / `26.3-1.0.12` | both | fabric-api, farmers-delight-refabricated |
| `mods/spark.pw.toml` | `spark` / `1.10.187` | both | fabric-api, irisshaders, modmenu, simple-voice-chat, sodium |
| `mods/spell-engine.pw.toml` | `spell_engine` / `1.10.9+26.3` | both | cloth-config, fabric-api, player-animation-library, spell-power |
| `mods/spell-power.pw.toml` | `spell_power` / `1.6.2+26.3` | both | fabric-api |
| `mods/status-effect-bars.pw.toml` | `status-effect-bars` / `1.0.12` | client | cloth-config |
| `mods/stoneworks.pw.toml` | `stoneworks` / `26.3.1` | both | fabric-api, forge-config-api-port, puzzles-lib |
| `mods/storage-delight-fabric.pw.toml` | `storagedelight` / `26.10.05-26.3-fabric` | both | fabric-api |
| `mods/strawberrylib.pw.toml` | `strawberrylib` / `26.3-r1` | both | fabric-api, irisshaders, modmenu, simple-voice-chat, sodium |
| `mods/structure-pool-api.pw.toml` | `structure_pool_api` / `1.3.0+26.3` | both | fabric-api |
| `mods/studious-keybinds.pw.toml` | `studiouskeybinds` / `1.0.3-beta.1` | client | Builtins / bundled only |
| `mods/supermartijn642s-core-lib.pw.toml` | `supermartijn642corelib` / `1.1.25` | both | fabric-api |
| `mods/swinging-lanterns.pw.toml` | `swinginglanterns` / `26.3-2.0.4` | client | fabric-api |
| `mods/tectonic.pw.toml` | `tectonic` / `3.0.31` | both | lithostitched |
| `mods/terralith.pw.toml` | `terralith` / `2.6.5` | both | lithostitched |
| `mods/timber-chests.pw.toml` | `timberchests` / `1.3.0` | both | fabric-api |
| `mods/toms-trees.pw.toml` | `mangatrees` / `1.0.0+26.3` | both | fabric-api |
| `mods/travelers-backpack-fabric.pw.toml` | `travelersbackpack` / `11.4.1` | both | fabric-api, forge-config-api-port |
| `mods/trinkets-updated.pw.toml` | `trinkets_updated` / `4.2.0+26.3` | both | fabric-api |
| `mods/ubes-delight.pw.toml` | `ubesdelight` / `0.4.15` | both | fabric-api, farmers-delight-refabricated, sodium |
| `mods/village-quest.pw.toml` | `village-quest` / `2.4.2` | both | fabric-api |
| `mods/village-taverns.pw.toml` | `village_taverns` / `1.3.1+26.3` | both | better-combat-by-daedelus, critical-strike, fabric-api, gazebos, jewelry, spell-engine, spell-power, structure-pool-api |
| `mods/villager-names.pw.toml` | `villagernames` / `8.7` | both | collective, fabric-api |
| `mods/waystones.pw.toml` | `waystones` / `26.3.0.1` | both | balm, fabric-api, shogi |
| `mods/weaponsexpanded.pw.toml` | `weaponsexpanded` / `2.1.2` | both | fabric-api |
| `mods/wilder-delights.pw.toml` | `wilderdelights` / `1.0.0-26.3` | both | delight-lib, fabric-api, farmers-delight-refabricated, wilder-wild |
| `mods/wilder-wild.pw.toml` | `wilderwild` / `4.3.2` | both | fabric-api, frozenlib |
| `mods/wizards.pw.toml` | `wizards` / `3.1.4+26.3` | both | armor-model-api, fabric-api, rune-crafting, spell-engine, structure-pool-api |
| `mods/xaeros-minimap.pw.toml` | `xaerominimap` / `26.6.0` | both | fabric-api, xaeros-world-map |
| `mods/xaeros-world-map.pw.toml` | `xaeroworldmap` / `1.47.0` | both | fabric-api, xaeros-minimap |
| `mods/yacl.pw.toml` | `yet_another_config_lib_v3` / `3.9.7+26.3-fabric` | both | fabric-api, modmenu, simple-voice-chat, sodium |
| `mods/zoomify.pw.toml` | `zoomify` / `2.17.0+mc26.3` | client | yacl |
