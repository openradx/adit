# pydicom and datetime
- To automatically convert dates to the datetime.date class this config must be set explicitly (default is False): config.datetime_conversion = True
- Then the type is valuerep.DA (https://pydicom.github.io/pydicom/dev/reference/generated/pydicom.valuerep.DA.html#) which is an instance of datetime.date
- Otherwise dates and times are represented as strings (e.g. 19760831)
- Same is true for datetime.time (valuerep.DT)

