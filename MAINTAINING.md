# תחזוקה

## הוספת סקיל

1. תיקייה חדשה ב-`plugins/ncode/skills/<שם-הסקיל>/` עם `SKILL.md`.
2. שורה בטבלה "מה יש כאן" ב-README, וסעיף קצר אם צריך הסבר.
3. להעלות את `version` בשני הקבצים: `.claude-plugin/marketplace.json` (פעמיים) ו-`plugins/ncode/.claude-plugin/plugin.json`.
4. לבדוק: `claude plugin validate .` ו-`npx skills add . --list`.
5. לפני שמעלים: אין בסקיל פרטים אישיים, מחירים, נתיבים מהמחשב של מישהו או מפתחות. מה שכל תלמיד צריך למלא בעצמו נכתב בסוגריים מרובעים.

## אם שם המכללה משתנה

השם מופיע רק במקומות האלה:

- `README.md`: הכותרת, הפסקה הראשונה והחתימה.
- `.claude-plugin/marketplace.json`: `owner` ו-`metadata.description`.
- `plugins/ncode/.claude-plugin/plugin.json`: `description` ו-`author`.

שם הפלאגין (`ncode`), שם המרקטפלייס (`ncode-skills`) ושם הריפו הם חלק מפקודות ההתקנה. אם משנים אותם, תלמידים שכבר התקינו צריכים להתקין מחדש, אז עדיף להשאיר אותם עד שיש סיבה טובה. GitHub מפנה לבד מכתובת ישנה של ריפו לכתובת החדשה.
