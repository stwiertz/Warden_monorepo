# Extraction d'images-clés éparses sur Android — recherche documentée

Contexte : Poco X5 Pro 5G (SM7325, Adreno 642L, Android 14), `c2.qti.avc.decoder`,
1061 images-clés H.264 1080p dans un MP4 de 2,3 Go. Mesure actuelle : **33,1 ms/image-clé,
35,1 s au total**, décodage = 99 % du mur.

Statut de chaque affirmation : **[M]** mesuré par vous, **[D]** dérivé de vos mesures par
arithmétique, **[S]** source vérifiable citée, **[I]** inféré (mécanisme sourcé, ordre de
grandeur non mesuré).

---

## 1. Verdict

**35 s n'est pas le plancher de la plateforme. C'est le prix d'un choix d'architecture :
un `flush()` + un aller-retour `END_OF_STREAM` par image-clé.**

Un chemin crédible vers **6 à 9 s** existe et ne demande qu'une réécriture de la boucle de
décodage, sans démultiplexeur maison ni parallélisme. Un chemin vers **~5 s** existe en
ajoutant un démultiplexeur MP4 maison. Le plancher dérivé de vos propres chiffres est
**~4,7 s** (décodage ~4,3 ms + E/S ~0,4 ms par image-clé).

La raison pour laquelle le matériel ne bat le logiciel que de 8 % est maintenant explicable :
**vous ne mesurez pas le décodage.** Vous mesurez 1061 démarrages et arrêts de pipeline.

---

## 2. Le diagnostic : les 30 ms non attribuées

Vos deux stratégies mesurées se recoupent et donnent la décomposition sans nouvelle
instrumentation.

Faits de départ :

| grandeur | valeur | statut |
|---|---|---|
| parcours complet de la table des samples (`advance()` sur 265 176 samples) | 62,1 s | [M] |
| coût par `advance()` | 0,234 ms | [D] |
| stratégie A′ (passage unique, sans seek, sans flush, sans EOS), sur 60 images-clés | 62,820 ms/if | [M] |
| stratégie A (seek + flush + EOS par image-clé), sur 60 images-clés | 32,937 ms/if | [M] |
| seek absolu isolé | 2,9 ms | [M] |

**Dérivation A′.** Une image-clé tous les 250 samples, donc A′ démultiplexe 250 samples par
image-clé : `250 x 0,234 = 58,5 ms`. Le reste de A′ est le décodage exposé :
`62,8 - 58,5 = 4,3 ms/image-clé`. [D]

> **Le décodage matériel d'une IDR 1080p coûte au plus ~4,3 ms quand le pipeline reste plein.**
> Cohérent avec les 5–8 ms mesurés par Moonlight en 1080p sur Snapdragon 870 [S].

**Dérivation A.** `32,9 = 2,9 (seek) + ~4,3 (décodage) + ~25,7 ms`. Ces 25,7 ms sont le
`flush()`, le vidage forcé par `END_OF_STREAM` et le redémarrage du pipeline. [D]

**Les ~30 ms non attribuées sont donc ~26 ms de démarrage/arrêt de pipeline et ~4 ms de
décodage réel.**

Mécanisme côté noyau, confirmé en source : un flush n'est pas une opération utilisateur, c'est
une commande HFI envoyée au firmware vidéo avec attente de `SESSION_FLUSH_DONE`
(`wait_for_completion_timeout(..., msm_vidc_hw_rsp_timeout)`) dans `msm_vidc_common.c` du
pilote `msm-extra/video-driver`. [S] Vous en payez 1061.

Et ce flush n'est pas optionnel dans votre conception actuelle : la documentation MediaCodec
impose que « Do not submit additional input buffers after signaling the end of the input
stream, unless the codec has been flushed, or stopped and restarted » [S]. **EOS force le
flush.** Les deux coûts sont le même coût.

Quant à « une seule image en entrée ne produit jamais rien en sortie », c'est documenté :
« it is possible that a codec may hold off on generating output buffers until all outstanding
buffers have been released/resubmitted » [S]. Ce n'est pas un bug, c'est la profondeur de
pipeline. La réponse n'est pas EOS, c'est de garder le pipeline plein.

---

## 3. Les pistes, chiffrées

Base de référence : 33,1 ms/image-clé, 35,1 s.

| # | piste | gain estimé | total visé | confiance | effort |
|---|---|---|---|---|---|
| 1 | **Boucle pipelinée : seeks, aucun flush, aucun EOS intermédiaire** | −26 ms/if | **~7 s** | haute (mécanisme), moyenne (chiffre) | 1–2 jours |
| 2 | `KEY_OPERATING_RATE` élevé | −1 à −3 ms/if | −1 à −3 s | moyenne | 2 lignes |
| 3 | `KEY_LOW_LATENCY` + extensions QTI | −0 à −2 ms/if | filet de sécurité | moyenne | 5 lignes |
| 4 | Démultiplexeur MP4 maison (stss/stsz/stco) | −2 à −2,6 ms/if | **~5 s** | haute | 3–5 jours |
| 5 | 2–4 instances de décodeur en parallèle | dépend de 1 | marginal après 1 | moyenne | 2–3 jours |
| 6 | Copie vers le stockage interne | **0** | — | **invalidée** | — |
| 7 | `MediaMetadataRetriever.getFrameAtIndex` | **négatif** | — | **invalidée** | — |

### Piste 1 — la seule qui compte : supprimer le flush et l'EOS

Remplacer « une image à la fois, drainée de force » par « N images-clés en vol, jamais de
flush, un seul EOS à la toute fin ».

Forme : mode **asynchrone** (`setCallback`), un `MediaExtractor` qui fait le seek suivant dès
qu'un buffer d'entrée se libère, 4 à 8 images-clés en vol, et un unique `END_OF_STREAM` après
la 1061e.

Est-ce correct d'enchaîner des IDR non contiguës sans flush ? **Oui.** Une image IDR force le
décodeur à marquer toutes les images de référence comme *unused for reference* — le DPB est
remis à zéro par la norme elle-même, c'est la définition d'un point d'accès aléatoire [S].
Le flush ne sert qu'à *jeter* ce qui est déjà en file, ce dont vous n'avez pas besoin puisque
vous consommez toutes les sorties. C'est d'ailleurs ce que fait AOSP lui-même : dans
`FrameDecoder.cpp`, la branche `isSeekingClosest` décode plusieurs samples d'affilée sans EOS
et s'appuie sur le pipeline [S].

Coût attendu par image-clé : `max(seek 2,2–2,9 ms, décodage ~4,3 ms)` puisque le décodage est
asynchrone et recouvre le seek → **~4,5 à 7 ms/image-clé, soit 5 à 8 s**. [I, à partir de [D]]

Deux garde-fous à prévoir :
- Ordre de sortie. Les PTS restent croissants, donc rien ne devrait se réordonner. En cas de
  doute, `vendor.qti-ext-dec-picture-order.enable = 1` force la sortie en ordre de décodage
  (utilisé par Moonlight sur les décodeurs `c2.qti`) [S].
- Latence de bout de pipeline. Les 4–8 dernières images arrivent après l'EOS final. Coût
  constant, amorti sur 1061.

### Piste 2 — `KEY_OPERATING_RATE`

Le pilote choisit la fréquence du cœur vidéo à partir de `operating_rate` si celui-ci dépasse
la cadence configurée :

```c
if (inst->clk_data.operating_rate > inst->clk_data.frame_rate)
    fps = (inst->clk_data.operating_rate >> 16) ? (inst->clk_data.operating_rate >> 16) : 1;
else
    fps = inst->clk_data.frame_rate >> 16;
```
`msm_vidc_get_fps()`, `msm_vidc_clocks.c` [S]

Par défaut votre format vient de l'extracteur et porte `frame-rate = 60`. Le cœur est donc
cadencé pour 60 images 1080p par seconde *en moyenne*. Or vous ne lui donnez que des images
intra, bien plus lourdes en bits que la moyenne d'un GOP. Monter `operating-rate` relève la
cible d'horloge.

C'est exactement ce que font les deux références du domaine :
- media3 `DefaultDecoderFactory.configureOperatingRate()` le règle sur la cadence maximale que
  le décodeur déclare supporter, recherchée par dichotomie jusqu'à 1024 fps, pour décoder plus
  vite que le temps réel [S].
- Moonlight le règle à `Short.MAX_VALUE` pour « reduce latency as much as possible on some
  Qualcomm platforms » [S].

⚠️ **Ne pas régler `KEY_PRIORITY = 0` sur cet appareil.** Moonlight documente des plantages
reproductibles avec la priorité temps réel sur Xiaomi Mi 10 lite 5G et Redmi K30i 5G, et
désactive l'option sur Adreno 620 [S]. Vous êtes sur un Xiaomi en Adreno 642L. Réglez
`operating-rate` seul.

### Piste 3 — `KEY_LOW_LATENCY`

Documentation : « If enabled, the decoder doesn't hold input and output data more than
required by the codec standards » [S]. Côté AOSP : « the decoder must return decoded frames
as soon as possible based on the coding standard (without waiting for further input) », et
sans ce mode « the decoder can use power optimizations that may result in decoded frames being
returned later than strictly necessary » [S].

**C'est la réponse directe et documentée à votre observation « une image en entrée ne sort
jamais ».** Sur un flux sans images B, le décodeur a le droit de sortir immédiatement ; il ne
le fait pas par économie d'énergie.

À vérifier sur l'appareil avant d'y compter : `c2.qti.avc.decoder` doit annoncer
`FEATURE_LowLatency`. Moonlight note que certains appareils exposent une variante séparée
`c2.qti.avc.decoder.low_latency`, et que des options non documentées existaient avant Android
11 (`vendor.qti-ext-dec-low-latency.enable`) [S]. Une sonde de 20 lignes tranche.

Avec la piste 1, ce mode n'est plus indispensable — mais il réduit la profondeur de pipeline,
donc la latence de queue, et il est gratuit.

### Piste 4 — démultiplexeur MP4 maison

**`MediaExtractor` sur-lit, c'est confirmé en source.** `NuMediaExtractor::fetchTrackSamples`
lit les données des samples à chaque `seekTo` *et* à chaque `advance()`, par lots :

```c
info->mMaxFetchCount = 8;   // pistes vidéo
...
err = info->mSource->readMultiple(&mediaBuffers, info->mMaxFetchCount, &options);
```
[S]

Conséquences :
1. Chaque seek lit jusqu'à **8 samples**, pas un : votre IDR de 200 Ko plus 7 images P inutiles.
2. `advance()` **n'est pas « metadata-only »** — le commentaire de
   [WardenKeyframeDecoder.kt:164](apps/mobile/plugins/kotlin/WardenKeyframeDecoder.kt#L164) est
   faux. C'est pourquoi le parcours complet coûte 62,1 s et lit les 2,3 Go.

Un démultiplexeur maison (stss + stsz + stsc + stco/co64 + ctts, plus `avcC` pour csd-0/csd-1,
et conversion des NAL préfixés en longueur vers les codes de départ Annex-B) lit exactement
210 Mo au lieu de 2,3 Go, supprime les allers-retours binder vers le processus
`media.extractor`, et remplace un seek de 2,2–2,9 ms par un `pread` de ~0,3–0,5 ms.

Bonus non négligeable : la table `stss` donne les 1061 PTS en une lecture. Vos **2,29 s** de
construction de liste par seeks disparaissent, et les **62,1 s** de parcours de vérification
aussi — à vérifier qu'il ne part pas en production, sinon il domine tout le reste.

Plancher d'E/S : 210 Mo en 1061 lectures de 200 Ko, sur UFS 2.2 mesurée à 810 Mo/s séquentiel
et 35 Mo/s aléatoire sur cet appareil précis → **~0,3 à 0,5 s au total**. [S + I]
L'E/S n'a jamais été le problème.

### Piste 5 — instances parallèles

Le CDD Android 13 impose **6 sessions de décodage matériel concurrentes en 1080p30** [S], donc
le SM7325 les supporte. Mais elles partagent un seul cœur vidéo : le parallélisme masque la
latence, il n'ajoute pas de débit. Puisque la piste 1 supprime précisément la latence
sérialisée, l'essentiel du gain est déjà pris. À garder en réserve, pas à faire en premier.

---

## 4. Hypothèses que la documentation invalide

**Le stockage FUSE (hypothèse 6) — invalidée, gain nul.**
Depuis Android 11, `Android/data/<pkg>` n'est pas servi par FUSE : `vold` le monte en bind
depuis le système de fichiers sous-jacent (`EmulatedVolume::mountFuseBindMounts`), et la
documentation AOSP le dit explicitement : « External private storage (which includes
android/data and android/obb directories) is bypassed by FUSE » [S]. Vos lectures touchent
déjà ext4/f2fs en direct. Copier 2,3 Go vers `/data` coûterait plusieurs secondes d'écriture
pour zéro gain en lecture.
Vérification en une commande : `adb shell run-as <pkg> grep Android /proc/self/mountinfo` —
vous devez voir `ext4`/`f2fs`, pas `fuse`.

**`MediaMetadataRetriever.getFrameAtIndex` (hypothèse 4) — invalidée, probablement plus lente.**
Le chemin interne est `FrameDecoder.cpp`, et il fait *exactement ce que vous faites déjà, en
pire* [S] :
- il pose `BUFFER_FLAG_EOS` par image, donc le même vidage de pipeline ;
- il **ne réutilise pas le codec** entre deux appels : une instance créée et détruite par image,
  soit bien plus cher qu'un flush ;
- il ajoute une conversion couleur vers RGB565/RGBA8888 sur le CPU dont vous n'avez pas besoin ;
- `getFramesAtIndex(index, n)` n'est optimisé que pour des images **consécutives** ; les vôtres
  sont espacées de 250.

Le seul élément réutilisable est son astuce de miniature : `android._num-input-buffers = 1` et
`android._num-output-buffers = 1` pour réduire la mise en mémoire tampon. C'est l'inverse de ce
qu'il vous faut.

Le sujet est connu côté Google : l'issue androidx/media #2714 s'intitule « Slow Frame
Extraction with MediaMetadataRetriever » [S].

**La mise à l'échelle d'horloge pilotée par l'espacement des PTS — non confirmée.**
J'ai instruit l'idée que des PTS espacés de 4,17 s feraient estimer au pilote une cadence
ridicule et rétrograderaient l'horloge. **Le code ne fait pas ça** : `msm_vidc_get_fps()` ne
lit que `frame_rate` (configuré) et `operating_rate` (espace utilisateur), jamais l'écart entre
horodatages [S]. L'hypothèse tombe — mais elle laisse la piste 2 intacte, qui agit sur le même
levier par la voie prévue.

**Le seek n'est pas cher (hypothèse implicite à corriger).**
2,9 ms sur 33 ms, et ce chiffre inclut la lecture disque de 8 samples. Le seek n'a jamais été
le problème ; le redémarrage du pipeline l'est.

---

## 5. Pistes auxquelles vous n'aviez pas pensé

1. **Poser `END_OF_STREAM` sur le buffer de l'image-clé elle-même**, au lieu d'un second buffer
   vide. AOSP fait ça : `*flags |= MediaCodec::BUFFER_FLAG_EOS` directement sur l'IDR dans
   `FrameDecoder::onInputReceived` [S]. Si vous gardez la conception actuelle pendant la
   transition, cela supprime un `dequeueInputBuffer` + `queueInputBuffer` par image-clé. Gain
   faible, coût nul.

2. **`TIMEOUT_US = 10 000` sur `dequeueOutputBuffer` dans une boucle synchrone.** À chaque tour
   où la sortie n'est pas prête, vous dormez potentiellement 10 ms. Avec un pipeline qui met
   plusieurs images à se remplir, c'est un quantum de 10 ms qui peut s'ajouter par image-clé.
   Le mode asynchrone de la piste 1 supprime la question ; en attendant, un timeout court
   (0 à 1000 µs) est plus sûr. À instrumenter avant d'y croire, mais c'est un suspect direct
   d'une partie des 25,7 ms.

3. **La sonde `countSyncSamplesByScan()` coûte 62,1 s.** Elle est légitime comme assertion de
   banc, mais elle doit être interdite en production, et elle disparaît entièrement avec la
   piste 4.

4. **Le défaut `SEEK_TO_NEXT_SYNC`** n'est pas expliqué par la lecture de
   `findSampleAtTime`/`findSyncSampleNear`, qui comparent en microsecondes après conversion et
   devraient donc honorer un `+1 µs` [S]. Je n'ai pas pu le reproduire en source. Non résolu —
   mais sans objet avec la piste 4, qui n'utilise plus l'API de seek du tout.

5. **media3 `FrameExtractor`** (ex-`ExperimentalFrameExtractor`, module `media3-inspector-frame`
   depuis la 1.10) fait ce travail en bibliothèque, avec conversion couleur sur GPU. Attention :
   il choisit **le décodeur logiciel par défaut**, parce que « some hardware MediaCodec decoders
   crash when flushing (seeking) » [S]. Utile comme témoin de comparaison, pas comme solution —
   et cette note sur les plantages au flush est un argument de plus pour ne plus flusher.

---

## 6. Ce qu'il faut mesurer avant d'écrire la version 2

La décomposition de la section 2 est dérivée, pas instrumentée. Quatre compteurs suffisent à
la confirmer ou à la démentir, dans la boucle actuelle :

1. `flush()` seul, horodaté, sur 100 itérations.
2. Temps entre le `queueInputBuffer` de l'IDR et le premier `dequeueOutputBuffer` positif.
3. Nombre de tours de boucle rendant `INFO_TRY_AGAIN_LATER` et temps cumulé dedans.
4. Octets réellement lus, via `/proc/self/io` (`read_bytes`) autour de la boucle. Attendu :
   ~2x la taille des I-frames sur le chemin seek, ~2,3 Go sur le chemin passage unique.

Si (1) + (3) ne totalisent pas ~25 ms, ma décomposition est fausse et il faut rouvrir le dossier.

---

## 7. Le levier produit, clairement séparé

Tout ce qui précède est technique. Le nombre d'images-clés analysées est un arbitrage produit,
et il est multiplicatif avec tout le reste :

- 1 image-clé sur 2 → temps divisé par 2, résolution temporelle 8,3 s au lieu de 4,2 s.
- Balayage grossier puis dense : 1 image-clé sur 4 pour situer les frontières de partie, puis
  densification uniquement autour des transitions détectées. Sur un enregistrement d'1 h 13
  majoritairement hors-partie, c'est potentiellement un facteur 3 à 4 pour une perte de
  résolution nulle là où elle compte.

À ne pas confondre avec une optimisation : c'est une décision de produit, et elle se prend
après la piste 1, pas à la place.

---

## 8. Réponse à la question posée

| cible | atteignable ? |
|---|---|
| **< 10 s** | **Oui.** Piste 1 seule, estimée 5–8 s. Confiance moyenne-haute. |
| **15–20 s** | Oui, avec marge, même si la piste 1 ne rend que la moitié du gain attendu. |
| **~5 s** | Plausible avec pistes 1 + 2 + 4. |
| **35 s est le plancher** | **Non.** Le plancher dérivé est ~4,7 s. |

Le décodage matériel n'a jamais été lent. Il n'a simplement jamais tourné plus de 4 ms d'affilée
avant qu'on ne lui coupe le pipeline.

---

## Sources

**Documentation Android**
- MediaCodec, gestion de fin de flux et rétention des buffers — https://developer.android.com/reference/android/media/MediaCodec
- `KEY_LOW_LATENCY`, `KEY_OPERATING_RATE`, `KEY_PRIORITY` — `MediaFormat.java`, https://github.com/aosp-mirror/platform_frameworks_base/blob/main/media/java/android/media/MediaFormat.java
- Low-latency decoding in MediaCodec — https://source.android.com/docs/core/media/low-latency-media
- Scoped storage, contournement de FUSE — https://source.android.com/docs/core/storage/scoped
- FUSE passthrough — https://source.android.com/docs/core/storage/fuse-passthrough
- CDD Android 13, sessions de décodage concurrentes — https://source.android.com/docs/compatibility/13/android-13-cdd

**Code source AOSP**
- `NuMediaExtractor.cpp` (`mMaxFetchCount = 8`, lecture des samples au seek et à l'advance) — https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/media/libstagefright/NuMediaExtractor.cpp
- `FrameDecoder.cpp` (chemin de `MediaMetadataRetriever`) — https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/media/libstagefright/FrameDecoder.cpp
- `SampleTable.cpp` (`findSampleAtTime`, `findSyncSampleNear`) — https://android.googlesource.com/platform/frameworks/av/+/refs/heads/main/media/module/extractors/mp4/SampleTable.cpp
- `EmulatedVolume.cpp` (bind mount de `Android/data`) — https://android.googlesource.com/platform/system/vold/+/refs/heads/main/model/EmulatedVolume.cpp

**Pilote noyau Qualcomm**
- `msm_vidc_clocks.c` (`msm_vidc_get_fps`, priorité de `operating_rate`) — https://android.googlesource.com/kernel/msm-extra/video-driver/+/refs/heads/android-msm-redbull-4.19-android12/msm/vidc/msm_vidc_clocks.c
- `msm_vidc_common.c` (flush = commande HFI avec attente firmware) — https://android.googlesource.com/kernel/msm-extra/video-driver/+/refs/heads/android-msm-redbull-4.19-android12/msm/vidc/msm_vidc_common.c

**Implémentations de référence**
- Moonlight `MediaCodecHelper.java` (operating rate, extensions QTI, plantages Xiaomi en priorité temps réel) — https://github.com/moonlight-stream/moonlight-android/blob/master/app/src/main/java/com/limelight/binding/video/MediaCodecHelper.java
- Moonlight `decoder-errata.txt` (variantes low latency Qualcomm) — https://github.com/moonlight-stream/moonlight-android/blob/master/decoder-errata.txt
- media3 `DefaultDecoderFactory` (operating rate maximal pour décodage hors temps réel) — https://github.com/androidx/media/blob/release/libraries/transformer/src/main/java/androidx/media3/transformer/DefaultDecoderFactory.java
- media3 `MediaCodecInfo.getMaxSupportedFrameRate` (recherche dichotomique jusqu'à 1024 fps) — https://github.com/androidx/media/blob/release/libraries/exoplayer/src/main/java/androidx/media3/exoplayer/mediacodec/MediaCodecInfo.java
- media3 `ExperimentalFrameExtractor` — https://github.com/androidx/media/blob/1.6.0/libraries/transformer/src/main/java/androidx/media3/transformer/ExperimentalFrameExtractor.java
- androidx/media issue #2714, lenteur de `MediaMetadataRetriever` — https://github.com/androidx/media/issues/2714

**Mesures publiées**
- Latence de décodage 1080p H.264 sur Snapdragon 870, 5–8 ms — https://github.com/moonlight-stream/moonlight-android/issues/1120
- Débits de stockage du Poco X5 Pro 5G (810 Mo/s séquentiel, 35 Mo/s aléatoire) — https://benchmarks.ul.com/hardware/phone/Xiaomi+Poco+X5+Pro+5G+review
