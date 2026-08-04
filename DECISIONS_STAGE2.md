I am writing my decisons here which i took over the project building. Its containing reason(why) and my judgemnt, decision, corrrection. As its not the requirement to write in proper format/sentences. I cant evn do, because time is short and also is not priority. Spending tim emore on things which matters


1. I've found a issue, currently, system is counting those records that  have not personal email/contact/linkedin. I need real way to reach the person, so dont count such records, that hold nothing from 3. drop it. Only count who have email or contact or linkedin.  build the 500 from firms whose website shows their people.
Why: because doc requires each record to reach named person

2. I found another issue, U are currently using only 1 source SEC form ADV. i need data to be collected from multiple sources but verified reliable. (CIK, EDGAR, Wikidata, news, ProPublica, OpenCorporates) these sources are in folder, but u didnt wired up, connect them and also use other sources to get dataset, but accurate

3.  I've seen records are alost empty. its just name, phone, or website. It has no recent activity, no idea what the firm invests in. A buyer needs to know why this firm matters and why now, but records are emty. So, Fill each record with real intelligence, recent news/activity and what they invest in. pulled from the firm's own site and news.

4.  I found issue in agent 2 in rag which using 2nd GROQ key, this agnet work is "Every detailed answer is cross-checked against the source records by a second model, which can flag or hold back anything the evidence doesn't fully support." so it was typo mistake on ui. So, I show real working of agent on ui.

5. Inclusion floor: It was doing only confirmed SFO counts, MFO auto-rejected, type-unknown auto-rejected. I found errorand now its FO-function proven = counts. Type labeled honestly: SFO / MFO / "type unresolved". Function-not-proven still rejected — proof-quote requirement untouched. Evidence that forced it: 4 of 89 qualified; ~16 of the 85 rejects had function proven but got killed on type alone. its side effect: 85 old rejects get requalified from stored evidence, not re-scraped

6. Source mix: it was climbing pool fed by SEC ADV roster (79/89) + Wikidata (10/89). i figured out issue, after fix and giving prompt now EDGAR full-text, ProPublica 990, OpenCorporates, news connectors also feed the pool. Each record keeps discovery_source

7. decided to test DDG LinkedIn search on 10 principals, wire in if it works.

8.  Decision: I use appolo, but free tier, to get contact data. I focused to find linked url first then email. Spend the limited email credits only on the strongest records. and pointed to make sure that Apollo enters like any source: through the pipeline, own validation (profile must match person + current firm), honest labels — provider-returned ≠ "verified". 
Why: because contact info isnt easily availbale on free sources. and websites block to scrap. 

9. I found dataset.csv + dataset_stage2.csv sit in the same final folder, its confusing about real product. so fixed Stage-1 files into an archive/stage1/ folder so final/ holds one dataset only.

10. Found file named "stale" inside final-product folder looks like shipped garbage. so, deleted it

11. I decided to making the robot climb to 500 records on its own (Apollo for contacts, faster runs, every 3h). also adding safety brains: it asks before risky decisions, double-checks its own answers, watches its spending, and replaces bad records automatically.

12. decided to remove all discarded api keys reference from code(like SNOv, etc). so no conflicting data confuse anyone.