"""Config manager — load/save MinimapConfig entries from config.yaml."""

import copy

import yaml

from .zone_model import MinimapConfig, Zone


class ConfigManager:
    """Manages minimap_identification config entries in a YAML file.

    Args:
        config_path: Path to config.yaml.
    """

    def __init__(self, config_path: str):
        self._path = config_path

    def _read_yaml(self) -> dict:
        with open(self._path, "r") as f:
            return yaml.safe_load(f) or {}

    def _write_yaml(self, data: dict):
        with open(self._path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def load(self) -> list[MinimapConfig]:
        data = self._read_yaml()
        entries = (
            data.get("minimap_identification", {}).get("configs", []) or []
        )
        configs = []
        for entry in entries:
            maps = {}
            for map_label, map_data in (entry.get("maps") or {}).items():
                zones = []
                for zd in map_data.get("zones", []):
                    hsv = zd.get("hsv", {})
                    zones.append(
                        Zone(
                            zone_id=zd["id"],
                            x=zd["x"],
                            y=zd["y"],
                            width=zd["width"],
                            height=zd["height"],
                            h_center=hsv.get("h_center", 0),
                            h_tol=hsv.get("h_tol", 180),
                            s_center=hsv.get("s_center", 0),
                            s_tol=hsv.get("s_tol", 12),
                            v_center=hsv.get("v_center", 100),
                            v_tol=hsv.get("v_tol", 15),
                            min_ratio=zd.get("min_ratio", 0.3),
                            weight=zd.get("weight", 0.0),
                            weight_override=zd.get("weight_override", False),
                        )
                    )
                maps[map_label] = zones
            configs.append(
                MinimapConfig(
                    id=entry["id"],
                    roi=entry.get("roi", {}),
                    identification_threshold=entry.get(
                        "identification_threshold", 0.6
                    ),
                    maps=maps,
                )
            )
        return configs

    def save(self, configs: list[MinimapConfig]):
        data = self._read_yaml()
        serialised = []
        for cfg in configs:
            maps_out = {}
            for map_label, zones in cfg.maps.items():
                zones_out = []
                for z in zones:
                    zones_out.append(
                        {
                            "id": z.zone_id,
                            "x": z.x,
                            "y": z.y,
                            "width": z.width,
                            "height": z.height,
                            "hsv": {
                                "h_center": z.h_center,
                                "h_tol": z.h_tol,
                                "s_center": z.s_center,
                                "s_tol": z.s_tol,
                                "v_center": z.v_center,
                                "v_tol": z.v_tol,
                            },
                            "min_ratio": z.min_ratio,
                            "weight": round(z.weight, 4),
                            "weight_override": z.weight_override,
                        }
                    )
                maps_out[map_label] = {"zones": zones_out}
            serialised.append(
                {
                    "id": cfg.id,
                    "roi": cfg.roi,
                    "identification_threshold": cfg.identification_threshold,
                    "maps": maps_out,
                }
            )
        if "minimap_identification" not in data:
            data["minimap_identification"] = {}
        data["minimap_identification"]["configs"] = serialised
        self._write_yaml(data)

    def upsert(self, config: MinimapConfig):
        configs = self.load()
        for i, c in enumerate(configs):
            if c.id == config.id:
                configs[i] = config
                self.save(configs)
                return
        configs.append(config)
        self.save(configs)

    def delete(self, config_id: str):
        configs = self.load()
        configs = [c for c in configs if c.id != config_id]
        self.save(configs)

    def clone(self, src_id: str, new_id: str) -> MinimapConfig:
        configs = self.load()
        src = None
        for c in configs:
            if c.id == src_id:
                src = c
                break
        if src is None:
            raise ValueError(f"Config '{src_id}' not found")
        cloned = copy.deepcopy(src)
        cloned.id = new_id
        return cloned
