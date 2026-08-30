/**
 * Plain names for machine constants. One dictionary, used everywhere.
 *
 * The console was readable only if you already knew the codebase. `AADHAAR` and
 * `QUASI_IDENTIFIER_SET` and `S1` and `origin: tool_definition` are all precise and
 * all opaque, and a security lead who has to ask what a word means stops reading.
 *
 * The rule this file follows: **keep the product's own nouns, drop the
 * implementation's.** A payload, a finding, a detector and a policy are what the
 * product calls things and the reader will meet those words again in the docs and
 * in a contract. A pipeline stage, a span path, an action lattice and a Verhoeff
 * check digit are how it is built, and the reader will never need them.
 *
 * Where a term genuinely carries meaning the audience knows - Aadhaar, PAN, GST -
 * it stays. Plain language is not the same as flattening the domain.
 */

// ------------------------------------------------------------- what was found --

/** Human name for an entity class. Falls back to a de-underscored version. */
export function thing(entityClass: string): string {
  return THINGS[entityClass] ?? entityClass.toLowerCase().replace(/_/g, ' ');
}

const THINGS: Record<string, string> = {
  // Keys and passwords
  ANTHROPIC_KEY: 'Anthropic key',
  OPENAI_KEY: 'OpenAI key',
  GITHUB_TOKEN: 'GitHub token',
  AWS_ACCESS_KEY: 'AWS key',
  AWS_SECRET_KEY: 'AWS secret',
  GOOGLE_API_KEY: 'Google API key',
  SLACK_TOKEN: 'Slack token',
  STRIPE_KEY: 'Stripe key',
  RAZORPAY_KEY: 'Razorpay key',
  JWT: 'Login token',
  PRIVATE_KEY: 'Private key',
  SSH_PRIVATE_KEY: 'SSH key',
  DB_URI: 'Database password',
  GENERIC_SECRET: 'Password or token',

  // Identity numbers
  PAN: 'PAN',
  AADHAAR: 'Aadhaar number',
  GSTIN: 'GST number',
  IFSC: 'Bank IFSC code',
  UPI_VPA: 'UPI ID',
  VOTER_ID: 'Voter ID',
  DL_NUMBER: 'Driving licence',

  // Money
  CREDIT_CARD: 'Card number',
  IBAN: 'IBAN',
  BANK_ACCOUNT: 'Bank account',

  // Contact
  EMAIL: 'Email address',
  PHONE: 'Phone number',
  ADDRESS: 'Address',
  PINCODE: 'PIN code',

  // People
  PERSON: 'Name',
  ORG: 'Organisation',
  GPE: 'Place',
  DATE_OF_BIRTH: 'Date of birth',
  AGE_BAND: 'Age',
  GENDER: 'Gender',

  // Categories that need clearance to read
  SECURITY_FINDING: 'Security finding',
  INCIDENT_REPORT: 'Incident report',
  INFRA_SECRET: 'Infrastructure secret',
  SOURCE_CODE_RESTRICTED: 'Restricted source code',
  CUSTOMER_DATA: 'Customer data',
  HR_RECORD: 'HR record',
  LEGAL_PRIVILEGED: 'Privileged legal document',
  FINANCIAL_RECORD: 'Financial record',

  // The two that most needed a name
  HIGH_ENTROPY_STRING: 'Random-looking text',
  QUASI_IDENTIFIER_SET: 'Personal record',
  UNKNOWN: 'Unclassified',
};

/** The group a class belongs to. What a reader would sort these into themselves. */
export function group(family: string): string {
  return GROUPS[family] ?? family.toLowerCase().replace(/_/g, ' ');
}

const GROUPS: Record<string, string> = {
  CREDENTIAL: 'Keys and passwords',
  INDIA_ID: 'Identity numbers',
  FINANCIAL: 'Bank and card details',
  CONTACT: 'Contact details',
  PERSON_DATA: 'Personal details',
  SENSITIVE_CATEGORY: 'Confidential documents',
  LOW_CONFIDENCE: 'Weak signals',
  COMPOSITE: 'Personal records',
  RESERVED: 'Unclassified',
};

// -------------------------------------------------------------- how it caught --

/**
 * The three ways the product finds something, named by what it looks at.
 *
 * These were S0, S1 and S2, which tell a reader the order they run in and nothing
 * about what they do. What they do is the interesting part and the reason the third
 * one exists at all.
 */
export function howFound(stage: string): string {
  return {
    S0: 'By its shape',
    S1: 'By the field it sits in',
    S2: 'By what surrounds it',
    S3: 'By what surrounds it',
  }[stage] ?? stage;
}

export function howFoundLong(stage: string): string {
  return {
    S0: 'A key or an ID number has a recognisable shape, so it is matched directly.',
    S1: 'A password has no shape at all. This one reads the field name around it - a value under “DB_PASSWORD” is a password whatever it looks like.',
    S2: 'A twelve-digit number means nothing on its own. Beside a name, a date of birth and a district it is somebody’s record, and this is the only thing that reaches it.',
  }[stage] ?? '';
}

// ------------------------------------------------------------ what was done --

/** What happened to the payload, in the past tense, as a person would say it. */
export function outcome(action: string): string {
  return {
    allow: 'Sent as-is',
    warn: 'Sent, and noted',
    tokenize: 'Replaced, then sent',
    mask: 'Hidden, then sent',
    block: 'Stopped',
  }[action] ?? action;
}

/** What the rule tells the product to do, in the present tense. */
export function instruction(action: string): string {
  return {
    allow: 'Let through',
    warn: 'Let through, note it',
    tokenize: 'Swap for a stand-in',
    mask: 'Hide it',
    block: 'Stop the request',
  }[action] ?? action;
}

// ---------------------------------------------------------------- where from --

/** Which part of the request a finding sat in. */
export function place(origin: string): string {
  return {
    user: 'Something the person typed',
    assistant: 'Something the AI wrote',
    system: 'Setup instructions',
    tool_definition: 'A tool’s description',
    tool_result: 'Data a tool fetched',
    tool_call: 'A tool being called',
    metadata: 'Technical fields',
  }[origin] ?? origin.replace(/_/g, ' ');
}

// ------------------------------------------------------------------- numbers --

/**
 * A share, said the way people say shares.
 *
 * "0.06% of payloads" is a number nobody can picture. "1 in 1,700" is the same fact
 * and it lands. Used for the small rates - anything under a twentieth.
 */
export function oneIn(fraction: number): string {
  if (fraction <= 0) return 'none';
  if (fraction >= 0.05) return `${(fraction * 100).toFixed(1)}%`;
  const n = Math.round(1 / fraction);
  return `1 in ${n.toLocaleString('en-IN')}`;
}

/** Microseconds as a reader would think of them. */
export function speed(us: number): string {
  if (us < 1000) return `${Math.round(us)} millionths of a second`;
  return `${(us / 1000).toFixed(1)} ms`;
}
