# Red Shed – Hack for Humanity 

## What this is
A static, mobile-friendly prototype for Challenge #1:
"Get a Canberran who thinks rowing isn't for them from first click into a boat within seven days, while minimising staff-written emails."

The MVP focuses on:
1. A Learn to Row microsite
2. "Find My Rowing Path" decision flow
3. Common concern answers
4. A chatbot-style FAQ prototype
5. A clear hand-off to Red Shed's current Learn to Row booking page
6. Semantic HTML + FAQ structured data for better machine readability

## Open it
Double-click `index.html`.

No installation is required.

## Important
The chatbot in this package is a rule-based demo so the front-end works without an API key.
Do NOT put an OpenAI API key directly into `script.js` or any browser file.

For a real AI chatbot:
- keep this front-end
- add a small secure backend endpoint
- connect the backend to the AI provider
- give the model only approved Red Shed knowledge
- require it to say when it does not know
- route safety/eligibility exceptions to staff

## Content basis
The prototype was drafted from:
- Red Shed Learn to Row page
- Red Shed Learn to Row Guide
- Red Shed FAQs / Get Started pages
- the supplied six-month customer enquiry research

Before public deployment, Red Shed should verify all copy and rules.

## Next hackathon tasks
- Replace text logo with approved Red Shed branding/assets if permission is given
- Add current Learn to Row course availability from the real booking source
- Add analytics events for: pathway started, pathway completed, FAQ opened, booking CTA clicked
- Connect a real AI chatbot backend
- Test with the enquiry scenarios from the supplied research
