#!/usr/bin/env python3
"""Select EC2 capacity inputs for the disposable Ubuntu Terraform stack."""

from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)

ARM64_DEFAULT_FAMILIES = ("t4g", "m7g", "c7g", "r7g")
AMD64_DEFAULT_FAMILIES = ("t3", "t3a", "m7i", "m7a", "c7i", "c7a", "r7i", "r7a")
HOURS_PER_MONTH = 24 * 365.25 / 12
PRICING_API_REGION = "us-east-1"
TERRAFORM_ARCHITECTURES = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64"}
SPOT_HISTORY_BUFFER_HOURS = 2
SPOT_SORT_CHOICES = (
    "score",
    "spot-price",
    "discount",
    "savings",
    "on-demand-price",
    "vcpu",
    "memory",
)


class AwsCache:
    """Small JSON cache for AWS capacity discovery calls."""

    def __init__(self, root: Path, *, enabled: bool, refresh: bool) -> None:
        self.root = root
        self.enabled = enabled
        self.refresh = refresh

    def get(self, key: str, *, ttl_hours: float | None) -> Any | None:
        value, _ = self.get_entry(key, ttl_hours=ttl_hours)
        return value

    def get_entry(
        self, key: str, *, ttl_hours: float | None
    ) -> tuple[Any | None, datetime | None]:
        if not self.enabled or self.refresh:
            return None, None
        path = self.root / f"{key}.json"
        if not path.is_file():
            return None, None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            return None, None
        cached_at = _parse_timestamp(str(payload.get("cached_at", "")))
        if (
            ttl_hours is not None
            and cached_at is not None
            and datetime.now(UTC) - cached_at > timedelta(hours=ttl_hours)
        ):
            return None, cached_at
        return payload.get("value"), cached_at

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self.root / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": datetime.now(UTC).isoformat(),
            "value": value,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


class ProgressReporter:
    """TTY-aware progress reporter that keeps stdout reserved for JSON."""

    def __init__(self, mode: bool | None) -> None:
        self.enabled = sys.stderr.isatty() if mode is None else mode
        self.console = Console(stderr=True)
        self.progress: Progress | None = None

    def __enter__(self) -> ProgressReporter:
        if self.enabled:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeRemainingColumn(),
                console=self.console,
                transient=False,
            )
            self.progress.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self.progress is not None:
            self.progress.stop()

    def add_task(self, description: str, *, total: int) -> TaskID | None:
        if self.progress is None:
            return None
        return self.progress.add_task(description, total=total)

    def advance(
        self, task_id: TaskID | None, *, description: str | None = None
    ) -> None:
        if self.progress is None or task_id is None:
            return
        fields: dict[str, object] = {"advance": 1}
        if description is not None:
            fields["description"] = description
        self.progress.update(task_id, **fields)

    def complete(
        self, task_id: TaskID | None, *, description: str | None = None
    ) -> None:
        if self.progress is None or task_id is None:
            return
        task = self.progress.tasks[task_id]
        total = task.total or task.completed
        fields: dict[str, object] = {"completed": total}
        if description is not None:
            fields["description"] = description
        self.progress.update(task_id, **fields)


def _default_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "dev-container-fortress" / "aws-capacity"
    return Path.home() / ".cache" / "dev-container-fortress" / "aws-capacity"


def _cache_key(*parts: object) -> str:
    safe_parts = []
    for part in parts:
        safe = str(part).replace("/", "_").replace(":", "_").replace(",", "_")
        safe_parts.append(safe)
    return "/".join(safe_parts)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _run_aws(region: str, args: list[str]) -> dict[str, Any]:
    command = ["aws", "--region", region, *args, "--output", "json"]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = _last_non_empty_line(result.stderr or result.stdout)
        raise RuntimeError(detail or f"aws command failed: {' '.join(command)}")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as error:
        raise RuntimeError("aws command did not return valid JSON") from error
    if not isinstance(payload, dict):
        raise RuntimeError("aws command returned a non-object JSON payload")
    return payload


def _last_non_empty_line(output: str) -> str:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _terraform_architecture(api_architecture: str) -> str:
    if api_architecture == "x86_64":
        return "amd64"
    return api_architecture


def _instance_terraform_architecture(instance_type_record: dict[str, Any]) -> str:
    supported_architectures = instance_type_record.get("ProcessorInfo", {}).get(
        "SupportedArchitectures", []
    )
    if "arm64" in supported_architectures:
        return "arm64"
    if "x86_64" in supported_architectures:
        return "amd64"
    raise RuntimeError(
        f"instance type {instance_type_record.get('InstanceType')} does not support arm64 or x86_64"
    )


def _normalize_architecture(value: str) -> str:
    try:
        return TERRAFORM_ARCHITECTURES[value]
    except KeyError as error:
        raise argparse.ArgumentTypeError(
            "architecture must be one of: amd64, x86_64, arm64"
        ) from error


def _families(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _matches_family_patterns(family: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(family, pattern) for pattern in patterns)


def _family_pattern_rank(family: str, patterns: list[str]) -> int:
    for index, pattern in enumerate(patterns):
        if fnmatch.fnmatch(family, pattern):
            return index
    return len(patterns)


def _default_families_for_architecture(architecture: str | None) -> list[str]:
    if architecture == "arm64":
        return list(ARM64_DEFAULT_FAMILIES)
    if architecture == "x86_64":
        return list(AMD64_DEFAULT_FAMILIES)
    return []


def _chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _default_subnets(
    region: str, cache: AwsCache, reporter: ProgressReporter, *, ttl_hours: float
) -> dict[str, str]:
    task_id = reporter.add_task("default VPC subnets", total=1)
    cache_key = _cache_key(region, "default-subnets")
    cached = cache.get(cache_key, ttl_hours=ttl_hours)
    if isinstance(cached, dict):
        reporter.complete(task_id, description="default VPC subnets cached")
        return {str(key): str(value) for key, value in cached.items()}

    vpcs = _run_aws(
        region,
        ["ec2", "describe-vpcs", "--filters", "Name=is-default,Values=true"],
    ).get("Vpcs", [])
    if not vpcs:
        raise RuntimeError(f"no default VPC found in {region}")
    vpc_id = str(vpcs[0]["VpcId"])
    subnets = _run_aws(
        region,
        ["ec2", "describe-subnets", "--filters", f"Name=vpc-id,Values={vpc_id}"],
    ).get("Subnets", [])
    subnet_by_az = {
        str(subnet["AvailabilityZone"]): str(subnet["SubnetId"])
        for subnet in subnets
        if subnet.get("AvailabilityZone") and subnet.get("SubnetId")
    }
    if not subnet_by_az:
        raise RuntimeError(f"no default VPC subnets found in {region}")
    cache.set(cache_key, subnet_by_az)
    reporter.complete(
        task_id, description=f"default VPC subnets fetched ({len(subnet_by_az)} AZs)"
    )
    return subnet_by_az


def _instance_type_records(
    *,
    region: str,
    architecture: str | None,
    current_generation: bool,
    cache: AwsCache,
    reporter: ProgressReporter,
    ttl_hours: float,
) -> list[dict[str, Any]]:
    task_id = reporter.add_task("instance type metadata", total=1)
    cache_key = _cache_key(
        region,
        "instance-types",
        architecture or "all-architectures",
        "current" if current_generation else "all-generations",
    )
    cached = cache.get(cache_key, ttl_hours=ttl_hours)
    if isinstance(cached, list):
        reporter.complete(
            task_id,
            description=f"instance type metadata cached ({len(cached)} records)",
        )
        return [item for item in cached if isinstance(item, dict)]

    filters = ["Name=bare-metal,Values=false"]
    if architecture is not None:
        filters.append(
            f"Name=processor-info.supported-architecture,Values={architecture}"
        )
    if current_generation:
        filters.append("Name=current-generation,Values=true")
    payload = _run_aws(
        region,
        ["ec2", "describe-instance-types", "--filters", *filters],
    )
    records = [
        item for item in payload.get("InstanceTypes", []) if isinstance(item, dict)
    ]
    cache.set(cache_key, records)
    reporter.complete(
        task_id, description=f"instance type metadata fetched ({len(records)} records)"
    )
    return records


def _candidate_instance_types(
    *,
    region: str,
    architecture: str | None,
    min_vcpu: int,
    min_memory_gib: float,
    max_vcpu: int | None,
    max_memory_gib: float | None,
    families: list[str],
    exclude_families: list[str],
    current_generation: bool,
    cache: AwsCache,
    reporter: ProgressReporter,
    ttl_hours: float,
) -> list[dict[str, Any]]:
    records = _instance_type_records(
        region=region,
        architecture=architecture,
        current_generation=current_generation,
        cache=cache,
        reporter=reporter,
        ttl_hours=ttl_hours,
    )
    minimum_memory_mib = int(min_memory_gib * 1024)
    maximum_memory_mib = (
        int(max_memory_gib * 1024) if max_memory_gib is not None else None
    )
    candidates = []
    for item in records:
        instance_type = str(item["InstanceType"])
        family = instance_type.split(".", maxsplit=1)[0]
        if families and not _matches_family_patterns(family, families):
            continue
        if _matches_family_patterns(family, exclude_families):
            continue
        vcpu = int(item["VCpuInfo"]["DefaultVCpus"])
        memory_mib = int(item["MemoryInfo"]["SizeInMiB"])
        if vcpu < min_vcpu or memory_mib < minimum_memory_mib:
            continue
        if max_vcpu is not None and vcpu > max_vcpu:
            continue
        if maximum_memory_mib is not None and memory_mib > maximum_memory_mib:
            continue
        candidates.append(
            {
                "instance_type": instance_type,
                "family": family,
                "architecture": _instance_terraform_architecture(item),
                "vcpu": vcpu,
                "memory_gib": round(memory_mib / 1024, 3),
            }
        )
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            item["vcpu"],
            item["memory_gib"],
            _family_pattern_rank(str(item["family"]), families),
            item["instance_type"],
        ),
    )
    task_id = reporter.add_task("candidate filters", total=1)
    reporter.complete(
        task_id,
        description=f"candidate filters matched ({len(sorted_candidates)} types)",
    )
    return sorted_candidates


def _monthly_price(hourly_price: float) -> float:
    return hourly_price * HOURS_PER_MONTH


def _extract_on_demand_price(price_item: dict[str, Any]) -> float | None:
    terms = price_item.get("terms", {}).get("OnDemand", {})
    if not isinstance(terms, dict):
        return None
    for term in terms.values():
        price_dimensions = term.get("priceDimensions", {})
        if not isinstance(price_dimensions, dict):
            continue
        for dimension in price_dimensions.values():
            price_per_unit = dimension.get("pricePerUnit", {})
            if not isinstance(price_per_unit, dict):
                continue
            usd_price = price_per_unit.get("USD")
            if usd_price is None:
                continue
            return float(usd_price)
    return None


def _aws_cli_next_token(payload: dict[str, Any]) -> str | None:
    token = payload.get("NextToken") or payload.get("nextToken")
    return str(token) if token else None


def _regional_on_demand_price_catalog(
    region: str,
    cache: AwsCache,
    reporter: ProgressReporter,
    *,
    ttl_hours: float,
) -> dict[str, float]:
    cache_key = _cache_key(region, "on-demand-price-catalog")
    cached = cache.get(cache_key, ttl_hours=ttl_hours)
    if isinstance(cached, dict):
        prices = {str(key): float(value) for key, value in cached.items()}
        task_id = reporter.add_task("on-demand price catalog", total=1)
        reporter.complete(
            task_id,
            description=f"on-demand price catalog cached ({len(prices)} prices)",
        )
        return prices

    task_id = reporter.add_task("on-demand price catalog", total=1)
    common_filters = [
        "Type=TERM_MATCH,Field=productFamily,Value=Compute Instance",
        f"Type=TERM_MATCH,Field=regionCode,Value={region}",
        "Type=TERM_MATCH,Field=operatingSystem,Value=Linux",
        "Type=TERM_MATCH,Field=tenancy,Value=Shared",
        "Type=TERM_MATCH,Field=preInstalledSw,Value=NA",
        "Type=TERM_MATCH,Field=capacitystatus,Value=Used",
    ]
    prices: dict[str, float] = {}
    next_token: str | None = None
    pages = 0
    while True:
        command = [
            "pricing",
            "get-products",
            "--service-code",
            "AmazonEC2",
            "--filters",
            *common_filters,
            "--max-results",
            "100",
        ]
        if next_token is not None:
            command.extend(["--next-token", next_token])
        try:
            payload = _run_aws(PRICING_API_REGION, command)
        except RuntimeError:
            reporter.complete(
                task_id,
                description=f"on-demand price catalog unavailable ({len(prices)} prices)",
            )
            return prices
        pages += 1
        for price_payload in payload.get("PriceList", []):
            if isinstance(price_payload, str):
                try:
                    price_item = json.loads(price_payload)
                except json.JSONDecodeError:
                    continue
            elif isinstance(price_payload, dict):
                price_item = price_payload
            else:
                continue
            attributes = price_item.get("product", {}).get("attributes", {})
            instance_type = attributes.get("instanceType")
            if not instance_type:
                continue
            price = _extract_on_demand_price(price_item)
            if price is not None:
                prices[str(instance_type)] = price
        reporter.complete(
            task_id,
            description=f"on-demand price catalog fetching ({len(prices)} prices, {pages} pages)",
        )
        next_token = _aws_cli_next_token(payload)
        if next_token is None:
            break
    cache.set(cache_key, prices)
    reporter.complete(
        task_id,
        description=f"on-demand price catalog complete ({len(prices)} prices, {pages} pages)",
    )
    return prices


def _on_demand_prices(
    region: str,
    instance_types: list[str],
    cache: AwsCache,
    reporter: ProgressReporter,
    *,
    ttl_hours: float,
) -> dict[str, float]:
    catalog = _regional_on_demand_price_catalog(
        region, cache, reporter, ttl_hours=ttl_hours
    )
    prices = {
        instance_type: catalog[instance_type]
        for instance_type in instance_types
        if instance_type in catalog
    }
    task_id = reporter.add_task("on-demand pricing", total=1)
    reporter.complete(
        task_id,
        description=f"on-demand pricing matched ({len(prices)}/{len(instance_types)} prices)",
    )
    return prices


def _with_on_demand_prices(
    *,
    region: str,
    candidates: list[dict[str, Any]],
    cache: AwsCache,
    reporter: ProgressReporter,
    ttl_hours: float,
) -> list[dict[str, Any]]:
    prices = _on_demand_prices(
        region,
        [str(candidate["instance_type"]) for candidate in candidates],
        cache,
        reporter,
        ttl_hours=ttl_hours,
    )
    enriched = []
    for candidate in candidates:
        item = dict(candidate)
        on_demand_price = prices.get(str(candidate["instance_type"]))
        item["on_demand_price"] = on_demand_price
        item["on_demand_price_monthly"] = (
            _monthly_price(on_demand_price) if on_demand_price is not None else None
        )
        enriched.append(item)
    return enriched


def _filter_on_demand_price_ceiling(
    candidates: list[dict[str, Any]], max_on_demand_hourly: float | None
) -> list[dict[str, Any]]:
    if max_on_demand_hourly is None:
        return candidates
    return [
        candidate
        for candidate in candidates
        if candidate.get("on_demand_price") is not None
        and float(candidate["on_demand_price"]) <= max_on_demand_hourly
    ]


def _spot_price_history(
    *,
    region: str,
    instance_types: list[str],
    lookback_hours: int,
    cache: AwsCache,
    reporter: ProgressReporter,
    workers: int,
    fresh_ttl_minutes: float,
) -> list[dict[str, Any]]:
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(hours=lookback_hours)
    records: list[dict[str, Any]] = []
    task_id = reporter.add_task("spot price history", total=len(instance_types))
    total_fresh = 0
    max_workers = max(1, min(workers, len(instance_types)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_by_instance_type = {
            executor.submit(
                _spot_price_history_for_instance_type,
                region=region,
                instance_type=instance_type,
                start_time=start_time,
                end_time=end_time,
                cache=cache,
                fresh_ttl_minutes=fresh_ttl_minutes,
            ): instance_type
            for instance_type in instance_types
        }
        for future in concurrent.futures.as_completed(future_by_instance_type):
            instance_records, fresh_count, cache_hit = future.result()
            records.extend(instance_records)
            total_fresh += fresh_count
            reporter.advance(
                task_id,
                description=(
                    f"spot price history {len(records)} retained, "
                    f"+{total_fresh} fetched"
                    f"{' (cache hit)' if cache_hit else ''}"
                ),
            )
    reporter.complete(
        task_id,
        description=(
            f"spot price history complete ({len(records)} retained, "
            f"+{total_fresh} fetched, {max_workers} workers)"
        ),
    )
    return records


def _spot_price_history_for_instance_type(
    *,
    region: str,
    instance_type: str,
    start_time: datetime,
    end_time: datetime,
    cache: AwsCache,
    fresh_ttl_minutes: float,
) -> tuple[list[dict[str, Any]], int, bool]:
    cache_key = _cache_key(region, "spot-history", instance_type)
    cached, cached_at = cache.get_entry(cache_key, ttl_hours=None)
    cached_records = (
        [item for item in cached if isinstance(item, dict)]
        if isinstance(cached, list)
        else []
    )
    cache_hit = bool(cached_records)
    if (
        cache_hit
        and cached_at is not None
        and cache.enabled
        and not cache.refresh
        and datetime.now(UTC) - cached_at <= timedelta(minutes=fresh_ttl_minutes)
    ):
        merged = _merge_spot_history(cached_records, [], start_time=start_time)
        return merged, 0, True
    query_start = start_time
    if cached_records and cache.enabled and not cache.refresh:
        timestamps = [
            parsed
            for parsed in (
                _parse_timestamp(str(record.get("Timestamp", "")))
                for record in cached_records
            )
            if parsed is not None
        ]
        if timestamps:
            query_start = max(
                start_time, max(timestamps) - timedelta(hours=SPOT_HISTORY_BUFFER_HOURS)
            )

    fresh_records: list[dict[str, Any]] = []
    if not cache.enabled or cache.refresh or query_start < end_time:
        payload = _run_aws(
            region,
            [
                "ec2",
                "describe-spot-price-history",
                "--instance-types",
                instance_type,
                "--product-descriptions",
                "Linux/UNIX",
                "--start-time",
                query_start.isoformat(),
                "--end-time",
                end_time.isoformat(),
            ],
        )
        fresh_records = [
            item
            for item in payload.get("SpotPriceHistory", [])
            if isinstance(item, dict)
        ]

    merged = _merge_spot_history(cached_records, fresh_records, start_time=start_time)
    cache.set(cache_key, merged)
    return merged, len(fresh_records), cache_hit


def _merge_spot_history(
    cached_records: list[dict[str, Any]],
    fresh_records: list[dict[str, Any]],
    *,
    start_time: datetime,
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in [*cached_records, *fresh_records]:
        timestamp = _parse_timestamp(str(record.get("Timestamp", "")))
        if timestamp is None or timestamp < start_time:
            continue
        key = (
            str(record.get("InstanceType", "")),
            str(record.get("AvailabilityZone", "")),
            timestamp.isoformat(),
        )
        normalized = dict(record)
        normalized["Timestamp"] = timestamp.isoformat()
        merged[key] = normalized
    return sorted(
        merged.values(),
        key=lambda record: (
            str(record.get("InstanceType", "")),
            str(record.get("AvailabilityZone", "")),
            str(record.get("Timestamp", "")),
        ),
    )


def _instance_type_offerings(
    *,
    region: str,
    instance_types: list[str],
    cache: AwsCache,
    reporter: ProgressReporter,
    ttl_hours: float,
) -> dict[str, set[str]]:
    offerings: dict[str, set[str]] = defaultdict(set)
    missing_instance_types: list[str] = []
    task_id = reporter.add_task("instance type offerings", total=len(instance_types))
    cache_hits = 0
    for instance_type in instance_types:
        cache_key = _cache_key(region, "offerings", instance_type)
        cached = cache.get(cache_key, ttl_hours=ttl_hours)
        if isinstance(cached, list):
            offerings[instance_type].update(str(item) for item in cached)
            cache_hits += 1
            reporter.advance(
                task_id,
                description=f"instance type offerings {cache_hits} cached",
            )
        else:
            missing_instance_types.append(instance_type)
    for chunk in _chunked(missing_instance_types, 100):
        payload = _run_aws(
            region,
            [
                "ec2",
                "describe-instance-type-offerings",
                "--location-type",
                "availability-zone",
                "--filters",
                f"Name=instance-type,Values={','.join(chunk)}",
            ],
        )
        for offering in payload.get("InstanceTypeOfferings", []):
            offerings[str(offering["InstanceType"])].add(str(offering["Location"]))
        for _ in chunk:
            reporter.advance(
                task_id,
                description=(
                    f"instance type offerings {cache_hits} cached, "
                    f"{len(missing_instance_types)} fetched"
                ),
            )
    for instance_type in missing_instance_types:
        cache.set(
            _cache_key(region, "offerings", instance_type),
            sorted(offerings[instance_type]),
        )
    reporter.complete(
        task_id,
        description=(
            f"instance type offerings complete ({len(instance_types)} types, "
            f"{cache_hits} cached)"
        ),
    )
    return offerings


def _rank_spot_candidates(
    *,
    region: str,
    candidates: list[dict[str, Any]],
    subnet_by_az: dict[str, str],
    lookback_hours: int,
    min_samples: int,
    max_hourly_price: float | None,
    max_spot_monthly: float | None,
    volatility_weight: float,
    sort_by: str,
    cache: AwsCache,
    reporter: ProgressReporter,
    workers: int,
    spot_history_fresh_ttl_minutes: float,
) -> list[dict[str, Any]]:
    details_by_type = {str(item["instance_type"]): item for item in candidates}
    history = _spot_price_history(
        region=region,
        instance_types=list(details_by_type),
        lookback_hours=lookback_hours,
        cache=cache,
        reporter=reporter,
        workers=workers,
        fresh_ttl_minutes=spot_history_fresh_ttl_minutes,
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in history:
        grouped[(str(record["InstanceType"]), str(record["AvailabilityZone"]))].append(
            record
        )

    ranked = []
    for (instance_type, availability_zone), records in grouped.items():
        if availability_zone not in subnet_by_az:
            continue
        if len(records) < min_samples:
            continue
        prices = [float(record["SpotPrice"]) for record in records]
        latest_record = max(records, key=lambda record: str(record["Timestamp"]))
        latest_price = float(latest_record["SpotPrice"])
        if max_hourly_price is not None and latest_price > max_hourly_price:
            continue
        if (
            max_spot_monthly is not None
            and _monthly_price(latest_price) > max_spot_monthly
        ):
            continue
        stdev = statistics.pstdev(prices) if len(prices) > 1 else 0.0
        detail = details_by_type[instance_type]
        on_demand_price = detail.get("on_demand_price")
        spot_savings_per_hour = (
            float(on_demand_price) - latest_price
            if on_demand_price is not None
            else None
        )
        spot_discount_pct = (
            (spot_savings_per_hour / float(on_demand_price)) * 100
            if on_demand_price not in {None, 0} and spot_savings_per_hour is not None
            else None
        )
        ranked.append(
            {
                **detail,
                "market": "spot",
                "availability_zone": availability_zone,
                "subnet_id": subnet_by_az[availability_zone],
                "latest_spot_price": latest_price,
                "latest_spot_price_monthly": _monthly_price(latest_price),
                "avg_spot_price": sum(prices) / len(prices),
                "avg_spot_price_monthly": _monthly_price(sum(prices) / len(prices)),
                "min_spot_price": min(prices),
                "max_spot_price": max(prices),
                "spot_price_stdev": stdev,
                "spot_savings_per_hour": spot_savings_per_hour,
                "spot_savings_monthly": (
                    _monthly_price(spot_savings_per_hour)
                    if spot_savings_per_hour is not None
                    else None
                ),
                "spot_discount_pct": spot_discount_pct,
                "sample_count": len(records),
                "score": latest_price + (stdev * volatility_weight),
                "latest_price_timestamp": str(latest_record["Timestamp"]),
            }
        )
    return _sort_spot_candidates(
        ranked,
        sort_by=sort_by,
    )


def _sort_spot_candidates(
    candidates: list[dict[str, Any]], *, sort_by: str
) -> list[dict[str, Any]]:
    def none_last(value: object, *, descending: bool = False) -> float:
        if value is None:
            return float("-inf") if descending else float("inf")
        return float(value)

    match sort_by:
        case "score":
            return sorted(
                candidates,
                key=lambda item: (
                    none_last(item.get("score")),
                    none_last(item.get("latest_spot_price")),
                    item["vcpu"],
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "spot-price":
            return sorted(
                candidates,
                key=lambda item: (
                    none_last(item.get("latest_spot_price")),
                    none_last(item.get("score")),
                    item["vcpu"],
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "discount":
            return sorted(
                candidates,
                key=lambda item: (
                    -none_last(item.get("spot_discount_pct"), descending=True),
                    none_last(item.get("latest_spot_price")),
                    item["vcpu"],
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "savings":
            return sorted(
                candidates,
                key=lambda item: (
                    -none_last(item.get("spot_savings_per_hour"), descending=True),
                    none_last(item.get("latest_spot_price")),
                    item["vcpu"],
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "on-demand-price":
            return sorted(
                candidates,
                key=lambda item: (
                    none_last(item.get("on_demand_price")),
                    none_last(item.get("latest_spot_price")),
                    item["vcpu"],
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "vcpu":
            return sorted(
                candidates,
                key=lambda item: (
                    -int(item["vcpu"]),
                    none_last(item.get("latest_spot_price")),
                    item["memory_gib"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case "memory":
            return sorted(
                candidates,
                key=lambda item: (
                    -float(item["memory_gib"]),
                    none_last(item.get("latest_spot_price")),
                    item["vcpu"],
                    item["instance_type"],
                    item["availability_zone"],
                ),
            )
        case _:
            raise RuntimeError(f"unsupported sort-by value: {sort_by}")


def _select_on_demand(
    *,
    region: str,
    candidates: list[dict[str, Any]],
    subnet_by_az: dict[str, str],
    cache: AwsCache,
    reporter: ProgressReporter,
    ttl_hours: float,
) -> dict[str, Any]:
    if not candidates:
        raise RuntimeError("no on-demand candidates matched the requested spec")
    offerings = _instance_type_offerings(
        region=region,
        instance_types=[str(candidate["instance_type"]) for candidate in candidates],
        cache=cache,
        reporter=reporter,
        ttl_hours=ttl_hours,
    )
    for candidate in candidates:
        offered_azs = offerings.get(str(candidate["instance_type"]), set())
        for availability_zone in sorted(subnet_by_az):
            if availability_zone not in offered_azs:
                continue
            selected = dict(candidate)
            selected.update(
                {
                    "market": "on-demand",
                    "availability_zone": availability_zone,
                    "subnet_id": subnet_by_az[availability_zone],
                }
            )
            return selected
    raise RuntimeError("no on-demand candidates are offered in default VPC subnets")


def _tfvars_for_selection(selected: dict[str, Any]) -> dict[str, Any]:
    is_spot = selected["market"] == "spot"
    payload: dict[str, Any] = {
        "instance_type": selected["instance_type"],
        "architecture": selected["architecture"],
        "subnet_id": selected["subnet_id"],
        "enable_spot": is_spot,
        "spot_max_price": None,
    }
    if is_spot:
        payload["spot_max_price"] = f"{float(selected['latest_spot_price']) * 1.10:.5f}"
    return payload


def select_capacity(args: argparse.Namespace) -> dict[str, Any]:
    cache = AwsCache(args.cache_root, enabled=args.cache, refresh=args.refresh_cache)
    families = (
        args.families
        if args.families is not None
        else _default_families_for_architecture(args.architecture)
    )
    with ProgressReporter(args.progress) as reporter:
        candidates = _candidate_instance_types(
            region=args.region,
            architecture=args.architecture,
            min_vcpu=args.min_vcpu,
            min_memory_gib=args.min_memory_gib,
            max_vcpu=args.max_vcpu,
            max_memory_gib=args.max_memory_gib,
            families=families,
            exclude_families=args.exclude_families,
            current_generation=not args.include_previous_generation,
            cache=cache,
            reporter=reporter,
            ttl_hours=args.instance_types_cache_ttl_hours,
        )
        if args.instance_type:
            candidates = [
                item
                for item in candidates
                if item["instance_type"] == args.instance_type
            ]
        if not candidates:
            raise RuntimeError("no instance types matched the requested spec")
        candidates = _with_on_demand_prices(
            region=args.region,
            candidates=candidates,
            cache=cache,
            reporter=reporter,
            ttl_hours=args.pricing_cache_ttl_hours,
        )
        candidates = _filter_on_demand_price_ceiling(
            candidates, args.max_on_demand_hourly
        )
        if not candidates:
            raise RuntimeError(
                "no instance types matched the requested price/spec ceilings"
            )

        subnet_by_az = _default_subnets(
            args.region,
            cache,
            reporter,
            ttl_hours=args.subnets_cache_ttl_hours,
        )
        if args.market == "on-demand":
            selected = _select_on_demand(
                region=args.region,
                candidates=candidates,
                subnet_by_az=subnet_by_az,
                cache=cache,
                reporter=reporter,
                ttl_hours=args.offerings_cache_ttl_hours,
            )
            ranked = [selected]
        else:
            ranked = _rank_spot_candidates(
                region=args.region,
                candidates=candidates,
                subnet_by_az=subnet_by_az,
                lookback_hours=args.lookback_hours,
                min_samples=args.min_samples,
                max_hourly_price=args.max_hourly_price,
                max_spot_monthly=args.max_spot_monthly,
                volatility_weight=args.volatility_weight,
                sort_by=args.sort_by,
                cache=cache,
                reporter=reporter,
                workers=args.workers,
                spot_history_fresh_ttl_minutes=args.spot_history_fresh_ttl_minutes,
            )
            if not ranked:
                raise RuntimeError("no spot candidates had usable price history")
            selected = ranked[0]

    tfvars = _tfvars_for_selection(selected)
    return {
        "region": args.region,
        "market": args.market,
        "requested": {
            "architecture": (
                _terraform_architecture(args.architecture)
                if args.architecture is not None
                else None
            ),
            "min_vcpu": args.min_vcpu,
            "min_memory_gib": args.min_memory_gib,
            "max_vcpu": args.max_vcpu,
            "max_memory_gib": args.max_memory_gib,
            "max_on_demand_hourly": args.max_on_demand_hourly,
            "max_spot_hourly": args.max_hourly_price,
            "max_spot_monthly": args.max_spot_monthly,
            "sort_by": args.sort_by,
            "families": families,
            "exclude_families": args.exclude_families,
            "lookback_hours": args.lookback_hours,
        },
        "cache": {
            "enabled": args.cache,
            "refresh": args.refresh_cache,
            "root": str(args.cache_root),
        },
        "selected": selected,
        "candidates": ranked[: args.top],
        "terraform_tfvars": tfvars,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select EC2 capacity inputs for aws-disposable-ubuntu."
    )
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--market", choices=("spot", "on-demand"), default="spot")
    parser.add_argument("--architecture", type=_normalize_architecture)
    parser.add_argument("--min-vcpu", type=int, default=2)
    parser.add_argument("--min-memory-gib", type=float, default=4.0)
    parser.add_argument("--max-vcpu", type=int)
    parser.add_argument("--max-memory-gib", type=float)
    parser.add_argument("--max-on-demand-hourly", type=float)
    parser.add_argument("--families", type=_families)
    parser.add_argument("--exclude-families", type=_families, default=[])
    parser.add_argument("--instance-type")
    parser.add_argument("--lookback-hours", type=int, default=168)
    parser.add_argument("--min-samples", type=int, default=2)
    parser.add_argument("--max-hourly-price", type=float)
    parser.add_argument("--max-spot-monthly", type=float)
    parser.add_argument("--sort-by", choices=SPOT_SORT_CHOICES, default="score")
    parser.add_argument("--volatility-weight", type=float, default=2.0)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--spot-history-fresh-ttl-minutes", type=float, default=15)
    parser.add_argument("--include-previous-generation", action="store_true")
    parser.add_argument("--cache", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--cache-root", type=Path, default=_default_cache_root())
    parser.add_argument("--instance-types-cache-ttl-hours", type=float, default=168)
    parser.add_argument("--subnets-cache-ttl-hours", type=float, default=1)
    parser.add_argument("--offerings-cache-ttl-hours", type=float, default=6)
    parser.add_argument("--pricing-cache-ttl-hours", type=float, default=24)
    parser.add_argument(
        "--progress", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument("--write-tfvars", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = select_capacity(args)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.write_tfvars is not None:
        args.write_tfvars.parent.mkdir(parents=True, exist_ok=True)
        args.write_tfvars.write_text(
            json.dumps(payload["terraform_tfvars"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
