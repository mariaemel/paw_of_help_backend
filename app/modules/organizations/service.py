import json
import re
from html import unescape

from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.animals.tags import species_label_ru
from app.modules.organizations.public_catalog import DEFAULT_HELP_SECTIONS, WARD_STATUS_PUBLIC_LABELS
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.schemas import (
    OrganizationCatalogsResponse,
    OrganizationFilterParams,
    OrganizationListItem,
    OrganizationListResponse,
    OrganizationPublicPage,
    OrgPublicAbout,
    OrgPublicArticle,
    OrgPublicEvent,
    OrgPublicHelpSection,
    OrgPublicHero,
    OrgPublicHomeStory,
    OrgPublicReport,
    OrgPublicUrgentNeed,
    OrgPublicWardCard,
    SocialLinkItem,
)


def _media_url(path: str | None) -> str | None:
    if not path or not str(path).strip():
        return None
    return f"{settings.media_url_prefix}/{path}"


def _parse_social_links(raw: str | None) -> list[SocialLinkItem]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[SocialLinkItem] = []
    for row in data[:3]:
        if not isinstance(row, dict):
            continue
        url = row.get("url")
        if not url:
            continue
        label = str(row.get("label") or row.get("platform") or "Ссылка")
        out.append(SocialLinkItem(label=label, url=str(url)))
    return out


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html_to_text(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    t = _HTML_TAG_RE.sub(" ", value)
    t = unescape(t)
    t = " ".join(t.split()).strip()
    return t or None


def _gallery_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    urls: list[str] = []
    for p in data[:5]:
        if isinstance(p, str) and p.strip():
            u = _media_url(p.strip())
            if u:
                urls.append(u)
    return urls


def _help_sections(org) -> list[OrgPublicHelpSection]:
    base: dict[str, dict[str, str]] = {row["kind"]: dict(row) for row in DEFAULT_HELP_SECTIONS}
    raw = getattr(org, "help_sections_json", None)
    if raw:
        try:
            over = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            over = None
        if isinstance(over, list):
            for row in over:
                if not isinstance(row, dict):
                    continue
                k = row.get("kind")
                if k not in base:
                    continue
                if row.get("title"):
                    base[k]["title"] = str(row["title"])
                if row.get("description") is not None:
                    base[k]["description"] = str(row["description"])
                if row.get("primary_action"):
                    base[k]["primary_action"] = str(row["primary_action"])
    return [OrgPublicHelpSection(**base[row["kind"]]) for row in DEFAULT_HELP_SECTIONS]


def _ward_status_label(code: str) -> str:
    return WARD_STATUS_PUBLIC_LABELS.get(code, code)


def _normalize_city_public(city: str | None) -> str | None:
    t = (city or "").strip()
    if not t:
        return None
    tl = t.lower()
    if tl == "москва":
        return "Екатеринбург"
    return t


def _public_region_for_city(city: str | None, region: str | None) -> str | None:
    c = _normalize_city_public(city)
    r_raw = (region or "").strip() or None
    if c and c.lower() == "екатеринбург":
        rl = (r_raw or "").lower()
        if not r_raw or rl == "екатеринбург":
            return "Свердловская область"
        if "свердловск" in rl:
            return "Свердловская область"
    return r_raw


def _public_city_region(city: str | None, region: str | None) -> tuple[str | None, str | None]:
    c_out = _normalize_city_public(city)
    r_out = _public_region_for_city(city, region)
    return c_out, r_out


def _geography_display(city: str | None, region: str | None, address: str | None) -> str | None:
    c, r = _public_city_region(city, region)
    c = (c or "").strip()
    r = (r or "").strip()
    parts: list[str] = []
    for x in (c, r):
        if x and x not in parts:
            parts.append(x)
    if parts:
        return ", ".join(parts)
    ad = (address or "").strip()
    return ad or None


def _pick_open_help_id(animal) -> int | None:
    best = None
    for hr in getattr(animal, "help_requests", []) or []:
        if getattr(hr, "status", "") != "open":
            continue
        if not getattr(hr, "is_published", False):
            continue
        if getattr(hr, "is_archived", False):
            continue
        if best is None:
            best = hr
        elif getattr(hr, "is_urgent", False) and not getattr(best, "is_urgent", False):
            best = hr
    return int(best.id) if best else None


class OrganizationService:
    def __init__(self, repo: OrganizationRepository):
        self.repo = repo

    def list_orgs(self, filters: OrganizationFilterParams) -> OrganizationListResponse:
        total, items = self.repo.list_organizations(filters)
        out: list[OrganizationListItem] = []
        for org in items:
            raw = org.needs_json or "[]"
            try:
                needs = json.loads(raw)
                if not isinstance(needs, list):
                    needs = []
            except json.JSONDecodeError:
                needs = []
            logo_path = getattr(org, "logo_path", None)
            out.append(
                OrganizationListItem(
                    id=org.id,
                    name=org.name,
                    city=org.city,
                    address=org.address,
                    specialization=org.specialization,
                    wards_count=org.wards_count,
                    adopted_yearly_count=org.adopted_yearly_count,
                    needs=[str(x) for x in needs],
                    logo_url=_media_url(logo_path) if logo_path else None,
                )
            )
        return OrganizationListResponse(total=total, items=out)

    def get_catalogs(self) -> OrganizationCatalogsResponse:
        cities, specs, needs_opts = self.repo.list_organization_catalogs()
        return OrganizationCatalogsResponse(
            cities=cities,
            specializations=specs,
            needs_options=needs_opts,
        )

    def get_public_page(self, organization_id: int) -> OrganizationPublicPage:
        org = self.repo.get_by_id(organization_id)
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

        city_out, region_out = _public_city_region(org.city, org.region)
        geography_display = _geography_display(org.city, org.region, org.address)

        hero = OrgPublicHero(
            name=org.name,
            tagline=org.tagline,
            description=org.description,
            city=city_out,
            region=region_out,
            geography_display=geography_display or org.address,
            address=org.address,
            phone=org.phone,
            email=org.email,
            social_links=_parse_social_links(getattr(org, "social_links_json", None)),
            logo_url=_media_url(getattr(org, "logo_path", None)),
            cover_url=_media_url(getattr(org, "cover_path", None)),
            wards_count=org.wards_count,
            adopted_yearly_count=org.adopted_yearly_count,
            has_chat_contact=bool(getattr(org, "has_chat_contact", False)),
            admission_rules=_strip_html_to_text(getattr(org, "admission_rules", None)),
            adoption_howto=_strip_html_to_text(getattr(org, "adoption_howto", None)),
        )

        wards: list[OrgPublicWardCard] = []
        for a in self.repo.list_public_wards(org.id):
            primary = next((p for p in a.photos if p.is_primary), None)
            if not primary and a.photos:
                primary = a.photos[0]
            photo_url = _media_url(primary.file_path) if primary else None
            st = getattr(a, "status", "") or ""
            wards.append(
                OrgPublicWardCard(
                    id=a.id,
                    name=a.name,
                    species=species_label_ru(getattr(a, "species", "cat"), a.sex),
                    age_months=int(getattr(a, "age_months", 0) or 0),
                    status=st,
                    status_label=_ward_status_label(st),
                    photo_url=photo_url,
                    is_urgent=bool(getattr(a, "is_urgent", False)),
                    open_help_request_id=_pick_open_help_id(a),
                )
            )

        gurls = _gallery_urls(getattr(org, "gallery_json", None))
        about_plain = _strip_html_to_text(getattr(org, "about_html", None))
        about_empty = not (
            bool(about_plain and about_plain.strip())
            or getattr(org, "founded_year", None)
            or gurls
            or getattr(org, "inn", None)
            or getattr(org, "ogrn", None)
            or getattr(org, "bank_account", None)
        )
        about = OrgPublicAbout(
            is_empty=about_empty,
            founded_year=getattr(org, "founded_year", None),
            about=about_plain,
            gallery_urls=gurls,
            inn=getattr(org, "inn", None),
            ogrn=getattr(org, "ogrn", None),
            bank_account=getattr(org, "bank_account", None),
        )

        open_req = self.repo.list_org_help_requests_open(org.id, limit=80)
        urgent_help = [
            OrgPublicUrgentNeed(
                id=r.id,
                title=r.title,
                description=r.description,
                help_type=r.help_type,
                is_urgent=bool(r.is_urgent),
                animal_id=r.animal_id,
                volunteer_needed=bool(r.volunteer_needed),
            )
            for r in open_req
            if r.is_urgent
        ]

        events_out: list[OrgPublicEvent] = []
        for e in self.repo.list_org_events(org.id):
            loc_bits = [x for x in (e.city or "", e.address or "") if x.strip()]
            events_out.append(
                OrgPublicEvent(
                    id=e.id,
                    title=e.title,
                    starts_at=e.starts_at,
                    ends_at=e.ends_at,
                    description=e.description,
                    location_display=", ".join(loc_bits) if loc_bits else None,
                )
            )

        reports_out = [
            OrgPublicReport(id=r.id, title=r.title, published_at=r.published_at, summary=r.summary)
            for r in self.repo.list_org_reports(org.id)
        ]

        articles_out: list[OrgPublicArticle] = []
        oid = getattr(org, "owner_user_id", None)
        if oid:
            for art in self.repo.list_org_articles_by_author(int(oid)):
                articles_out.append(
                    OrgPublicArticle(
                        id=art.id,
                        title=art.title,
                        category=art.category,
                        read_minutes=art.read_minutes,
                    )
                )

        stories_out = [
            OrgPublicHomeStory(
                id=s.id,
                animal_name=s.animal_name,
                story=s.story,
                photo_url=_media_url(s.photo_path),
                adopted_at=s.adopted_at,
            )
            for s in self.repo.list_org_home_stories(org.id)
        ]

        return OrganizationPublicPage(
            hero=hero,
            wards=wards,
            about=about,
            help_sections=_help_sections(org),
            urgent_help=urgent_help,
            events=events_out,
            reports=reports_out,
            articles=articles_out,
            home_stories=stories_out,
        )
