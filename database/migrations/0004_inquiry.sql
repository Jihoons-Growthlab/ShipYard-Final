-- F12 건의·문의, F13 챗봇 접수 멱등
CREATE TABLE TB_SYS_Inquiry (
  InquiryId INTEGER PRIMARY KEY AUTOINCREMENT,
  Category TEXT NOT NULL CHECK (Category IN ('BUG','FEATURE','QUESTION','ETC')),
  Title TEXT NOT NULL,
  Content TEXT NOT NULL,
  Status TEXT NOT NULL DEFAULT 'OPEN' CHECK (Status IN ('OPEN','IN_PROGRESS','DONE','REJECTED')),
  CreateUserId TEXT REFERENCES users (emp_no) ON DELETE SET NULL,
  CreateDt TEXT NOT NULL,
  ModifyDt TEXT,
  Answer TEXT,
  AnswerDt TEXT,
  AnswerUserId TEXT REFERENCES users (emp_no) ON DELETE SET NULL
);
CREATE INDEX ix_inquiry_user ON TB_SYS_Inquiry (CreateUserId);

CREATE TABLE TB_SYS_ChatInquiry (
  CreateUserId TEXT NOT NULL,
  RequestId TEXT NOT NULL,
  InquiryId INTEGER NOT NULL,
  Category TEXT NOT NULL,
  Content TEXT NOT NULL,
  PRIMARY KEY (CreateUserId, RequestId)
);
