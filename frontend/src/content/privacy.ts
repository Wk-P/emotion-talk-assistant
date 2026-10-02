// 用户隐私协议 — source text: documents/02_内容与需求/用户隐私协议.md (Chinese, as written
// by the research team). The Korean and English versions are translations
// of it; keep all three in step when one changes.
import type { UiLang } from '@/i18n/langPreference'

export interface PrivacySection {
  title: string
  body: string[]
}

export interface PrivacyDoc {
  title: string
  sections: PrivacySection[]
}

export const PRIVACY: Record<UiLang, PrivacyDoc> = {
  zh: {
    title: '《自我共情对话个人信息及隐私说明》',
    sections: [
      {
        title: '1. 服务说明',
        body: ['本应用通过生成式人工智能提供自我共情对话、自我理解、情绪整理及自我调节相关支持。'],
      },
      {
        title: '2. 收集和处理的信息',
        body: [
          '包括用户主动输入的对话内容、选择的情绪及强度、对话目的、调节活动选择、使用时间、保存的反思记录等。若提供注册功能，还可能处理账号所需的基本信息。',
        ],
      },
      {
        title: '3. 信息使用目的',
        body: [
          '所收集的信息主要用于提供AI对话、保存用户自主选择保存的记录、维持服务运行以及改善应用功能。若相关数据用于学术研究，将另外取得研究参与者的知情同意。',
        ],
      },
      {
        title: '4. AI服务与第三方处理',
        body: [
          '为生成对话回应，用户输入的部分内容可能通过API发送至AI服务提供商进行处理。根据 OpenAI 当前公开政策，其API业务数据默认不用于训练或改进模型，除非账户主动选择共享数据。',
        ],
      },
      {
        title: '5. 保存与删除',
        body: [
          '仅在实现服务所需的范围内保存信息，并根据服务目的及研究要求确定保存期限。用户可以查看、删除自己的保存记录，或撤回相关同意。',
        ],
      },
      {
        title: '6. 用户的选择与控制权',
        body: ['用户可以跳过非必要问题、中断对话、选择是否保存记录，并可以请求删除相关个人信息。'],
      },
      {
        title: '7. 信息安全',
        body: ['采取合理的技术及管理措施保护用户信息，并尽可能采用最小化收集、去标识化或匿名化方式处理研究数据。'],
      },
      {
        title: '8. 使用限制与安全说明',
        body: [
          '本应用不用于疾病诊断、心理治疗或医疗决策。AI生成内容可能存在错误或不完全适合个体情况，用户可以忽略、修改或停止使用相关建议。',
        ],
      },
      {
        title: '9. 危机情况',
        body: [
          '如果用户出现严重的自伤、自杀、伤害他人或其他紧急危险，应优先寻求现实中的专业和紧急支持，而不是依赖本应用。',
        ],
      },
      {
        title: '10. 联系与修改',
        body: ['研究负责人：肖爱进（XIAO AIJIN）', '邮箱：xiaoaijin12@gmail.com', '所属机构：Pusan National University'],
      },
    ],
  },
  ko: {
    title: '《자기공감 대화 개인정보 및 프라이버시 안내》',
    sections: [
      {
        title: '1. 서비스 안내',
        body: ['본 앱은 생성형 인공지능을 통해 자기공감 대화, 자기 이해, 감정 정리 및 자기 조절과 관련된 지원을 제공합니다.'],
      },
      {
        title: '2. 수집 및 처리하는 정보',
        body: [
          '사용자가 직접 입력한 대화 내용, 선택한 감정과 그 강도, 대화 목적, 조절 활동 선택, 이용 시간, 저장한 성찰 기록 등이 포함됩니다. 회원가입 기능을 제공하는 경우, 계정에 필요한 기본 정보도 처리될 수 있습니다.',
        ],
      },
      {
        title: '3. 정보 이용 목적',
        body: [
          '수집된 정보는 주로 AI 대화 제공, 사용자가 직접 저장을 선택한 기록의 보관, 서비스 운영 유지 및 앱 기능 개선에 사용됩니다. 관련 데이터를 학술 연구에 활용하는 경우, 연구 참여자로부터 별도의 동의를 받습니다.',
        ],
      },
      {
        title: '4. AI 서비스 및 제3자 처리',
        body: [
          '대화 응답을 생성하기 위해 사용자가 입력한 내용의 일부가 API를 통해 AI 서비스 제공업체로 전송되어 처리될 수 있습니다. OpenAI의 현재 공개 정책에 따르면, API 비즈니스 데이터는 계정에서 데이터 공유를 직접 선택하지 않는 한 기본적으로 모델 학습이나 개선에 사용되지 않습니다.',
        ],
      },
      {
        title: '5. 보관 및 삭제',
        body: [
          '서비스 제공에 필요한 범위 내에서만 정보를 보관하며, 보관 기간은 서비스 목적과 연구 요건에 따라 정합니다. 사용자는 자신이 저장한 기록을 확인·삭제하거나 관련 동의를 철회할 수 있습니다.',
        ],
      },
      {
        title: '6. 사용자의 선택권과 통제권',
        body: [
          '사용자는 필수가 아닌 질문을 건너뛰거나, 대화를 중단하거나, 기록 저장 여부를 선택할 수 있으며, 관련 개인정보의 삭제를 요청할 수 있습니다.',
        ],
      },
      {
        title: '7. 정보 보안',
        body: [
          '합리적인 기술적·관리적 조치를 통해 사용자 정보를 보호하며, 연구 데이터는 가능한 한 최소 수집, 가명화 또는 익명화 방식으로 처리합니다.',
        ],
      },
      {
        title: '8. 이용 제한 및 안전 안내',
        body: [
          '본 앱은 질병 진단, 심리 치료 또는 의료적 결정을 위한 것이 아닙니다. AI가 생성한 내용에는 오류가 있거나 개인의 상황에 완전히 맞지 않을 수 있으며, 사용자는 관련 제안을 무시하거나 수정하거나 이용을 중단할 수 있습니다.',
        ],
      },
      {
        title: '9. 위기 상황',
        body: [
          '심각한 자해, 자살, 타인에 대한 위해 또는 기타 긴급한 위험이 있는 경우, 본 앱에 의존하기보다 현실의 전문적·긴급 지원을 우선적으로 받아야 합니다.',
        ],
      },
      {
        title: '10. 연락처 및 변경',
        body: ['연구 책임자: XIAO AIJIN(肖爱进)', '이메일: xiaoaijin12@gmail.com', '소속 기관: 부산대학교 (Pusan National University)'],
      },
    ],
  },
  en: {
    title: 'Self-Compassion Talk — Personal Information and Privacy Notice',
    sections: [
      {
        title: '1. About the service',
        body: ['This app uses generative AI to support self-compassion conversations, self-understanding, sorting out emotions and self-regulation.'],
      },
      {
        title: '2. Information collected and processed',
        body: [
          'This includes conversation content you enter, the emotions and intensity you choose, the purpose of the conversation, the regulation activities you choose, usage times, and reflection records you save. Where registration is offered, the basic information needed for an account may also be processed.',
        ],
      },
      {
        title: '3. Purposes of use',
        body: [
          'The information is mainly used to provide AI conversations, keep the records you choose to save, run the service and improve the app. If the data is used for academic research, separate informed consent will be obtained from research participants.',
        ],
      },
      {
        title: '4. AI services and third-party processing',
        body: [
          'To generate replies, part of what you enter may be sent via an API to an AI service provider for processing. Under OpenAI’s current public policy, API business data is not used to train or improve models by default, unless the account opts in to sharing data.',
        ],
      },
      {
        title: '5. Retention and deletion',
        body: [
          'Information is kept only as far as needed to provide the service, and retention periods are set according to the purpose of the service and research requirements. You can view and delete your saved records, or withdraw the related consent.',
        ],
      },
      {
        title: '6. Your choices and control',
        body: ['You can skip non-essential questions, stop a conversation, choose whether to save records, and request deletion of your personal information.'],
      },
      {
        title: '7. Information security',
        body: ['Reasonable technical and organisational measures are taken to protect your information, and research data is processed with data minimisation, de-identification or anonymisation wherever possible.'],
      },
      {
        title: '8. Limitations and safety',
        body: [
          'This app is not for diagnosing illness, psychological treatment or medical decisions. AI-generated content may contain errors or may not fully fit your situation; you can ignore or change its suggestions, or stop using them.',
        ],
      },
      {
        title: '9. Crisis situations',
        body: [
          'If you are at serious risk of self-harm, suicide, harming others or any other emergency, please seek professional and emergency support in real life first rather than relying on this app.',
        ],
      },
      {
        title: '10. Contact and changes',
        body: ['Principal investigator: XIAO AIJIN (肖爱进)', 'Email: xiaoaijin12@gmail.com', 'Institution: Pusan National University'],
      },
    ],
  },
}
