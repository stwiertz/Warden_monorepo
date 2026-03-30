"""Zone validation engine — computes TP/FP rates, weights, and accuracy."""

from dataclasses import dataclass

from tools.frame_labeler import MAP_LABELS

from .zone_model import MinimapConfig, zone_fires


@dataclass
class ZoneStats:
    tp_rate: float       # fraction of same-map frames where zone fires
    fp_rate: float       # fraction of all other-map frames where zone fires
    auto_weight: float   # tp_rate * (1 - max FP rate across any single other map)


@dataclass
class MapStats:
    accuracy: float               # fraction of same-map frames correctly identified
    coverage_sim_accuracy: float  # worst-case accuracy with one zone knocked out


@dataclass
class ValidationResult:
    zone_stats: dict  # zone_id -> ZoneStats
    map_stats: dict   # map_label -> MapStats
    overall_accuracy: float


class ZoneValidator:

    @staticmethod
    def compute(config: MinimapConfig, loader) -> ValidationResult:
        """Run full validation of all zones against all labeled images.

        Args:
            config: The active MinimapConfig with zones per map.
            loader: MinimapDataLoader instance.

        Returns:
            ValidationResult with per-zone stats, per-map stats, and overall accuracy.
        """
        all_frames = loader.get_all_frames()

        # Pre-compute zone_fires() for every (zone, map, frame)
        # fires[map_label][zone_id][other_map] = list[bool]
        # Simpler: fires[zone_id][map_label] = list[bool]
        fires: dict[str, dict[str, list[bool]]] = {}

        for map_label in MAP_LABELS:
            zones = config.maps.get(map_label, [])
            for zone in zones:
                if zone.zone_id not in fires:
                    fires[zone.zone_id] = {}
                for frame_map in MAP_LABELS:
                    frames = all_frames.get(frame_map, [])
                    fires[zone.zone_id][frame_map] = [
                        zone_fires(zone, f) for f in frames
                    ]

        # Per-zone stats
        zone_stats: dict[str, ZoneStats] = {}
        for map_label in MAP_LABELS:
            zones = config.maps.get(map_label, [])
            for zone in zones:
                zf = fires.get(zone.zone_id, {})

                # TP rate: fires on same-map frames
                same_fires = zf.get(map_label, [])
                tp_rate = (
                    sum(same_fires) / len(same_fires) if same_fires else 0.0
                )

                # Per other-map FP rates
                max_other_fp = 0.0
                for other_map in MAP_LABELS:
                    if other_map == map_label:
                        continue
                    other_fires = zf.get(other_map, [])
                    if other_fires:
                        other_fp = sum(other_fires) / len(other_fires)
                        max_other_fp = max(max_other_fp, other_fp)

                auto_weight = tp_rate * (1.0 - max_other_fp)
                zone_stats[zone.zone_id] = ZoneStats(
                    tp_rate=tp_rate,
                    fp_rate=max_other_fp,
                    auto_weight=auto_weight,
                )

        # Per-map accuracy
        map_stats: dict[str, MapStats] = {}
        maps_with_frames = []

        for map_label in MAP_LABELS:
            frames = all_frames.get(map_label, [])
            zones = config.maps.get(map_label, [])

            if not frames:
                map_stats[map_label] = MapStats(accuracy=0.0, coverage_sim_accuracy=0.0)
                continue

            maps_with_frames.append(map_label)

            # Per-frame: sum weights of zones that fire
            correct_count = 0
            for fi in range(len(frames)):
                weighted_sum = 0.0
                for zone in zones:
                    zf = fires.get(zone.zone_id, {}).get(map_label, [])
                    if fi < len(zf) and zf[fi]:
                        weighted_sum += zone.weight
                if weighted_sum >= config.identification_threshold:
                    correct_count += 1

            accuracy = correct_count / len(frames)

            # Coverage simulation: knock out one zone at a time
            if len(zones) <= 1:
                coverage_sim = accuracy
            else:
                per_knockout = []
                for ki in range(len(zones)):
                    ko_correct = 0
                    for fi in range(len(frames)):
                        weighted_sum = 0.0
                        for zi, zone in enumerate(zones):
                            if zi == ki:
                                continue
                            zf = fires.get(zone.zone_id, {}).get(map_label, [])
                            if fi < len(zf) and zf[fi]:
                                weighted_sum += zone.weight
                        if weighted_sum >= config.identification_threshold:
                            ko_correct += 1
                    per_knockout.append(ko_correct / len(frames))
                coverage_sim = min(per_knockout)

            map_stats[map_label] = MapStats(
                accuracy=accuracy,
                coverage_sim_accuracy=coverage_sim,
            )

        # Overall accuracy: mean of maps with frames
        overall = (
            sum(map_stats[m].accuracy for m in maps_with_frames) / len(maps_with_frames)
            if maps_with_frames
            else 0.0
        )

        return ValidationResult(
            zone_stats=zone_stats,
            map_stats=map_stats,
            overall_accuracy=overall,
        )
