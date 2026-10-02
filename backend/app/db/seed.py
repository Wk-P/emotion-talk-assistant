"""Seeds CrisisResource with a starting set of Korea-based public hotlines.

IMPORTANT — before this app is used with real participants, the research team
MUST independently re-verify every contact below (number, hours, scope) against
the operating agency's current published information, and update `verified_at`
to the date that check was done. This seed only covers long-standing national
lines; it intentionally omits any university-specific counseling center, whose
contact must be filled in per-institution by the researcher, not guessed here.
Nothing here should ever be presented to a user without that human verification
step having happened at least once (design principle 8.4: the AI must not
invent or silently trust unverified contact details).
"""

import asyncio
from datetime import datetime, timezone

from app.db.session import async_session_maker, init_db
from app.models.resource import CrisisResource

_SEED_VERIFIED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)  # placeholder — replace on real verification

RESOURCES = [
    CrisisResource(
        id="kr-suicide-prevention-1393",
        country="KR",
        category="national_hotline",
        name={"zh": "自杀预防咨询电话 1393", "ko": "자살예방상담전화 1393", "en": "Suicide Prevention Hotline 1393"},
        description={
            "zh": "韩国保健福祉部运营的24小时自杀预防及危机咨询热线，免费，多语言支持需在通话中确认。",
            "ko": "보건복지부가 운영하는 24시간 자살예방 및 위기상담 전화. 무료이며, 다국어 지원 여부는 통화 중 확인이 필요합니다.",
            "en": "24-hour suicide prevention and crisis line run by the Ministry of Health and Welfare. Free; ask on the call whether other languages are available.",
        },
        contact="1393",
        url="https://www.129.go.kr",
        verified_at=_SEED_VERIFIED_AT,
    ),
    CrisisResource(
        id="kr-mental-health-crisis-1577-0199",
        country="KR",
        category="national_hotline",
        name={"zh": "精神健康危机咨询电话 1577-0199", "ko": "정신건강 위기상담전화 1577-0199", "en": "Mental Health Crisis Line 1577-0199"},
        description={
            "zh": "全国精神健康危机咨询热线，24小时运营。",
            "ko": "전국 정신건강 위기상담전화, 24시간 운영.",
            "en": "Nationwide mental health crisis line, open 24 hours.",
        },
        contact="1577-0199",
        url=None,
        verified_at=_SEED_VERIFIED_AT,
    ),
    CrisisResource(
        id="kr-foreigner-helpcenter-1345",
        country="KR",
        category="foreigner_support",
        name={"zh": "外国人综合服务中心 1345", "ko": "외국인종합안내센터 1345", "en": "Immigration Contact Center 1345"},
        description={
            "zh": "韩国法务部出入境·外国人政策本部运营，提供多语言生活咨询与信息引导（非心理危机专线，但可协助转介）。",
            "ko": "법무부 출입국·외국인정책본부 운영, 다국어 생활상담 및 정보안내(심리 위기 전용은 아니며 연계 지원 목적).",
            "en": "Run by the Korea Immigration Service; multilingual help with daily-life questions and information (not a crisis line, but can refer you on).",
        },
        contact="1345",
        url="https://www.hikorea.go.kr",
        verified_at=_SEED_VERIFIED_AT,
    ),
]


async def seed() -> None:
    await init_db()
    async with async_session_maker() as db:
        for resource in RESOURCES:
            await db.merge(resource)
        await db.commit()
    print(f"Seeded {len(RESOURCES)} crisis resources. Verify contacts before real use!")


if __name__ == "__main__":
    asyncio.run(seed())
