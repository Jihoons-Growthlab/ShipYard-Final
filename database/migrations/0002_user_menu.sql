-- BR-10 회원별 메뉴 권한
CREATE TABLE TB_SYS_UserMenu (
  EmpNo TEXT NOT NULL REFERENCES users (emp_no) ON DELETE CASCADE,
  MenuId TEXT NOT NULL REFERENCES TB_SYS_MenuInfo (MenuId) ON DELETE CASCADE,
  AuthGbn TEXT NOT NULL CHECK (AuthGbn IN ('None','View','Write','Admin')),
  PRIMARY KEY (EmpNo, MenuId)
);
