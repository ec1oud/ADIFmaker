# wsjtx-all2adif
A vibe-coded Python script to convert a WSJT-X ALL.TXT file into an ADI QSO log.
It's useful if you lost your ADI log somehow, or are using a buggy version of
some fork (like Decodium) that doesn't output a log but still outputs the ALL.TXT file.

Originally written by ChatGPT and fixed up later with Qwen 3.5.

The original author claimed that the original prompt was:

Please write me a python script to read a WSJT-X ALL.TXT file and output an ADIF log file of valid QSOs.
If necessary, please highlight what I need to change depending on whether the file is PC or Unix format.  

I imagine a regex will be required on the lines of the input file. I can't understand regex, but the format should be:

> <date time - two six digit integers separated by underscore> <Band Frequency - a floating point number> <"Rx" or "Tx" relative to me - string> <Mode - string> <Signal Strength - signed integer> <DT (I don't know what that is) - float> <Frequency Offset - unsigned integer> <Message - string>

With respect to <Message>, its format varies. It is typically (but not exclusively) any one of:

> CQ <Sender> <Locator>
> <Recipient> <Sender> <Locator>
> <Recipient> <Sender> <Signal Strength>
> <Recipient> <Sender> R<Signal Strength>
> <Recipient> <Sender> RR73
> <Recipient> <Sender> 73

It is generally accepted that if a message contains "73" it is likely to signify the end of a valid QSO. I only wish to log these.

Can you please also count:
- the lines which contribute to a log
- the lines which don't contribute to any log
- any lines which don't match the regex

What I mean by "count the lines which 'contribute' to a log" is that we can't count all the lines contianing 73 as signifying a valid QSO. A complete QSO (a "log entry")is a series of exchanges between <Recipient> and <Sender> and contains contains one (or more) of
> <Recipient> <Sender> RR73
> <Recipient> <Sender> 73

But don't forget that the recipient and sender might swap places. A complete conversation might go:

> CQ FRED MYLOCATION (I'm Fred, I want to talk to someone, I'm at MYLOCATION) 
> FRED GEORGE GEORGES_LOCATION (Hi, Fred, I'm George, I'm at GEORGES_LOCATION)
> GEORGE FRED +5 (Hi, George, this is Fred, your signal to me was +5)
> FRED GEORGE R+6 (Fred, This is George, Received, your signal to me was +6)
> GEORGE FRED RR73 (George, this is Fred, Roger, and regards)
> FRED GEORGE 73 (Fred, this is George, regards.)

(I put an English translation of the conversation in round brackets.)

Certain parts of the closing exchange migth be missing, but generally, it's a QSO when one or other party says "73".

So, we need to first isolate the lines which contian my callsign. Lets create a constant at the start of teh script MyCall = "M0ABC"

Here is a useful structure giving you the lower and upper frequencies in kHz and the names of the bands, so you can extract them

```
BANDS = (
  ('160m',1810,2000),
  ('80m',3500,3800),
  ('60m',5258.5,5406.5),
  ('40m',7000,7200),
  ('30m',10100,10150),
  ('20m',14000,14350),
  ('17m',18068,18168),
  ('15m',21000,21450),
  ('12m',24890,24990),
  ('10m',28000,29700),
  ('6m',50000,52000),
  ('4m',70000,70500),
  ('2m',144000,146000),
  ('70m',430000,440000) )
```

