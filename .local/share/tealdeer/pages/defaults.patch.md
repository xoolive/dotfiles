# defaults

- Reset default timezones in iCal

`defaults read com.apple.iCal 'RecentlyUsedTimeZones'`
`defaults write com.apple.iCal 'RecentlyUsedTimeZones' '("Europe/Paris", "Asia/Tokyo")'`

